"""
cli/cmd_snapshot.py — tscodekg snapshot subcommands.

Manage temporal snapshots of TypeScriptKG metrics:

  snapshot save   — capture current metrics and save snapshot
  snapshot list   — show all snapshots with key metrics
  snapshot show   — display full snapshot details
  snapshot diff   — compare two snapshots
  snapshot prune  — remove vestigial snapshots
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import click

logger = logging.getLogger(__name__)


@click.group("snapshot")
def snapshot() -> None:
    """Manage temporal snapshots of TypeScriptKG metrics."""


def _default_snapshots_dir(snapshots_dir: str | None, repo_root: Path | None = None) -> Path:
    base = repo_root if repo_root is not None else Path.cwd()
    return Path(snapshots_dir).resolve() if snapshots_dir else base / ".tscodekg" / "snapshots"


@snapshot.command("save")
@click.argument("version", metavar="VERSION", default="", required=False)
@click.option(
    "--repo",
    default=".",
    type=click.Path(exists=True),
    show_default=True,
    help="Repository root path.",
)
@click.option(
    "--db",
    default=None,
    type=click.Path(),
    help="SQLite knowledge graph path (default: <repo>/.tscodekg/graph.sqlite).",
)
@click.option(
    "--snapshots-dir",
    default=None,
    type=click.Path(),
    help="Snapshots directory (default: <repo>/.tscodekg/snapshots).",
)
@click.option(
    "--branch",
    default=None,
    type=str,
    help="Branch name; auto-detected if not provided.",
)
@click.option(
    "--tree-hash",
    default="",
    type=str,
    help="Git tree hash; auto-detected if not provided.",
)
def save_snapshot(
    version: str | None,
    repo: str,
    db: str | None,
    snapshots_dir: str | None,
    branch: str | None,
    tree_hash: str,
) -> None:
    """
    Capture current TypeScriptKG metrics and save as a temporal snapshot.

    Reads graph statistics and JSDoc coverage from the SQLite graph, runs the
    analyzer for issue counts and hotspots, then saves a snapshot tagged with
    the given VERSION.  The tree hash is auto-detected from git when not
    provided.

    Snapshots are stored in .tscodekg/snapshots/{tree_hash}.json, with a
    manifest.json tracking all snapshots and their metrics.

    Example:
        tscodekg snapshot save 0.1.0 --repo .
    """
    capture_snapshot(
        version=version,
        repo=repo,
        db=db,
        snapshots_dir=snapshots_dir,
        branch=branch,
        tree_hash=tree_hash,
    )


def capture_snapshot(
    *,
    version: str | None,
    repo: str,
    db: str | None,
    snapshots_dir: str | None,
    branch: str | None,
    tree_hash: str,
) -> None:
    """Capture and persist a snapshot; shared by ``snapshot save`` and ``init``.

    :param version: Version tag; auto-detected from the package when falsy.
    :param repo: Repository root path.
    :param db: SQLite graph path; defaults to ``<repo>/.tscodekg/graph.sqlite``.
    :param snapshots_dir: Snapshots directory; defaults to ``<repo>/.tscodekg/snapshots``.
    :param branch: Branch name; auto-detected when ``None``.
    :param tree_hash: Git tree hash; auto-detected when empty.
    """
    from tscode_kg.kg import TypeScriptKG  # pylint: disable=import-outside-toplevel
    from tscode_kg.snapshots import SnapshotManager  # pylint: disable=import-outside-toplevel

    repo_root = Path(repo).resolve()
    db_path = Path(db) if db else repo_root / ".tscodekg" / "graph.sqlite"
    snapshots_path = _default_snapshots_dir(snapshots_dir, repo_root)

    kg = TypeScriptKG(repo_root=repo_root, db_path=db_path)
    snap_mgr = SnapshotManager(snapshots_path, db_path=db_path)

    critical_issues = 0
    complexity_median = 0.0
    hotspots: list[dict] = []
    issue_strings: list[str] = []
    try:
        stats = kg.stats()

        # Run the analyzer for issues/hotspots; a snapshot must still be
        # capturable when the semantic index or kg extras are unavailable
        # (e.g. from the pre-commit hook on a graph-only build).
        try:
            from tscode_kg.analysis import (  # pylint: disable=import-outside-toplevel
                TSCodeKGAnalyzer,
            )

            analyzer = TSCodeKGAnalyzer(kg, snapshot_mgr=snap_mgr)
            analysis = analyzer.run_analysis()

            issue_strings = analysis.get("issues", [])
            critical_issues = len(issue_strings)

            fn_metrics = analysis.get("function_metrics", {})
            hotspots = [
                {
                    "name": name,
                    "callers": m.get("fan_in", 0),
                    "callees": m.get("fan_out", 0),
                }
                for name, m in list(fn_metrics.items())[:10]
            ]
            fan_ins = [m.get("fan_in", 0) for m in fn_metrics.values()]
            complexity_median = float(sorted(fan_ins)[len(fan_ins) // 2]) if fan_ins else 0.0
        except Exception as exc:  # noqa: BLE001
            logger.warning("Analyzer unavailable, capturing stats-only snapshot: %s", exc)
            click.echo(f"  (analyzer unavailable — stats-only snapshot: {exc})", err=True)
    finally:
        kg.close()

    snapshot_obj = snap_mgr.capture(
        version=version or None,
        branch=branch,
        graph_stats_dict=stats,
        critical_issues=critical_issues,
        complexity_median=complexity_median,
        hotspots=hotspots,
        issues=issue_strings,
        tree_hash=tree_hash,
    )

    snapshot_file = snap_mgr.save_snapshot(snapshot_obj)
    coverage = snapshot_obj.metrics.get("docstring_coverage") or 0.0
    click.echo(f"OK Snapshot saved: {snapshot_file}")
    click.echo(f"  Key:     {snapshot_obj.key}")
    click.echo(f"  Version: {snapshot_obj.version}")
    click.echo(f"  Nodes:   {snapshot_obj.metrics.get('total_nodes', 0)}")
    click.echo(f"  Edges:   {snapshot_obj.metrics.get('total_edges', 0)}")
    click.echo(f"  Coverage: {coverage:.1%}")


@snapshot.command("list")
@click.option(
    "--snapshots-dir",
    default=None,
    type=click.Path(exists=True),
    help="Snapshots directory (default: .tscodekg/snapshots).",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Max snapshots to show.",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output as JSON.",
)
def list_snapshots(snapshots_dir: str | None, limit: int | None, output_json: bool) -> None:
    """
    List all temporal snapshots in reverse chronological order.

    Shows key, timestamp, version, and key metrics (nodes, edges, coverage)
    for each snapshot.
    """
    from tscode_kg.snapshots import SnapshotManager  # pylint: disable=import-outside-toplevel

    mgr = SnapshotManager(_default_snapshots_dir(snapshots_dir))
    snapshots = mgr.list_snapshots(limit=limit)

    if not snapshots:
        click.echo("No snapshots found.")
        return

    if output_json:
        click.echo(json.dumps(snapshots, indent=2))
        return

    click.echo(
        f"{'Key':<12} {'Timestamp':<20} {'Branch':<12} {'Version':<8}"
        f" {'Nodes':<6} {'Edges':<6} {'Coverage':<9}"
    )
    click.echo("-" * 85)
    for snap in snapshots:
        key = snap["key"][:12]
        ts = snap["timestamp"]
        ts_display = ts[:16].replace("T", " ") if ts else "unknown"
        branch = (snap.get("branch") or "")[:12]
        version = (snap.get("version") or "")[:8]
        metrics = snap.get("metrics", {})
        nodes = metrics.get("total_nodes", 0)
        edges = metrics.get("total_edges", 0)
        coverage = metrics.get("docstring_coverage") or 0.0
        click.echo(
            f"{key:<12} {ts_display:<20} {branch:<12} {version:<8}"
            f" {nodes:<6} {edges:<6} {coverage:>6.1%}"
        )


@snapshot.command("show")
@click.argument("key", metavar="KEY")
@click.option(
    "--snapshots-dir",
    default=None,
    type=click.Path(exists=True),
    help="Snapshots directory (default: .tscodekg/snapshots).",
)
def show_snapshot(key: str, snapshots_dir: str | None) -> None:
    """
    Display full details for a single snapshot by key (tree hash).

    Shows all metrics, hotspots, and deltas vs. previous and baseline snapshots.
    """
    from tscode_kg.snapshots import SnapshotManager  # pylint: disable=import-outside-toplevel

    mgr = SnapshotManager(_default_snapshots_dir(snapshots_dir))
    snapshot_obj = mgr.load_snapshot(key)

    if not snapshot_obj:
        click.echo(f"Snapshot not found: {key}", err=True)
        raise click.Abort()

    metrics = snapshot_obj.metrics

    click.echo(f"Key:       {snapshot_obj.key}")
    click.echo(f"Branch:    {snapshot_obj.branch}")
    click.echo(f"Timestamp: {snapshot_obj.timestamp}")
    click.echo(f"Version:   {snapshot_obj.version}")
    click.echo()

    coverage = metrics.get("docstring_coverage") or 0.0
    click.echo("Metrics:")
    click.echo(f"  Total Nodes:       {metrics.get('total_nodes', 0)}")
    click.echo(f"  Total Edges:       {metrics.get('total_edges', 0)}")
    click.echo(f"  Meaningful Nodes:  {metrics.get('meaningful_nodes', 0)}")
    click.echo(f"  JSDoc Coverage:    {coverage:.1%}")
    click.echo(f"  Critical Issues:   {metrics.get('critical_issues', 0)}")
    click.echo(f"  Complexity Median: {metrics.get('complexity_median', 0.0):.2f}")
    click.echo()

    click.echo("Node/Edge Breakdown:")
    for kind, count in sorted(metrics.get("node_counts", {}).items()):
        click.echo(f"  {kind}: {count}")
    click.echo()
    for rel, count in sorted(metrics.get("edge_counts", {}).items()):
        click.echo(f"  {rel}: {count}")
    click.echo()

    if snapshot_obj.hotspots:
        click.echo("Top Hotspots (Fan-In):")
        for i, hotspot in enumerate(snapshot_obj.hotspots[:5], 1):
            name = hotspot.get("name", "unknown")
            callers = hotspot.get("callers", 0)
            click.echo(f"  {i}. {name} ({callers} callers)")
        click.echo()

    if snapshot_obj.vs_previous:
        delta = snapshot_obj.vs_previous
        click.echo("Delta vs. Previous:")
        click.echo(f"  Nodes:       {delta.get('nodes', 0):+d}")
        click.echo(f"  Edges:       {delta.get('edges', 0):+d}")
        click.echo()

    if snapshot_obj.vs_baseline:
        delta = snapshot_obj.vs_baseline
        click.echo("Delta vs. Baseline:")
        click.echo(f"  Nodes:       {delta.get('nodes', 0):+d}")
        click.echo(f"  Edges:       {delta.get('edges', 0):+d}")


@snapshot.command("diff")
@click.argument("key_a", metavar="KEY_A")
@click.argument("key_b", metavar="KEY_B")
@click.option(
    "--snapshots-dir",
    default=None,
    type=click.Path(exists=True),
    help="Snapshots directory (default: .tscodekg/snapshots).",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output as JSON.",
)
def diff_snapshots(key_a: str, key_b: str, snapshots_dir: str | None, output_json: bool) -> None:
    """
    Compare two snapshots side-by-side.

    Shows metrics from both snapshots and computed deltas (B - A).

    Example:
        tscodekg snapshot diff 660e4f0a 3487ed5b
    """
    from tscode_kg.snapshots import SnapshotManager  # pylint: disable=import-outside-toplevel

    mgr = SnapshotManager(_default_snapshots_dir(snapshots_dir))
    diff_result = mgr.diff_snapshots(key_a, key_b)

    if "error" in diff_result:
        click.echo(f"Error: {diff_result['error']}", err=True)
        raise click.Abort()

    if output_json:
        click.echo(json.dumps(diff_result, indent=2))
        return

    a = diff_result["a"]
    b = diff_result["b"]
    metrics_a = a["metrics"]
    metrics_b = b["metrics"]

    click.echo(f"Comparing {a['key'][:10]} vs {b['key'][:10]}")
    click.echo()
    click.echo(f"{'Metric':<20} {'A':<12} {'B':<12} {'Δ':<12}")
    click.echo("-" * 56)

    for metric_key in ["total_nodes", "total_edges", "meaningful_nodes"]:
        val_a = metrics_a.get(metric_key, 0)
        val_b = metrics_b.get(metric_key, 0)
        click.echo(f"{metric_key:<20} {val_a:<12} {val_b:<12} {val_b - val_a:+d}")

    cov_a = metrics_a.get("docstring_coverage") or 0.0
    cov_b = metrics_b.get("docstring_coverage") or 0.0
    click.echo(f"{'docstring_coverage':<20} {cov_a:<12.1%} {cov_b:<12.1%} {cov_b - cov_a:+.1%}")

    issues_a = metrics_a.get("critical_issues", 0)
    issues_b = metrics_b.get("critical_issues", 0)
    click.echo(f"{'critical_issues':<20} {issues_a:<12} {issues_b:<12} {issues_b - issues_a:+d}")


@snapshot.command("prune")
@click.option(
    "--snapshots-dir",
    default=None,
    type=click.Path(),
    help="Snapshots directory (default: .tscodekg/snapshots).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be removed without deleting anything.",
)
def prune_snapshots(snapshots_dir: str | None, dry_run: bool) -> None:
    """
    Remove vestigial snapshots that carry no new metric information.

    Cleans up three categories:

    \b
    1. Metric-duplicates — interior snapshots with unchanged metrics.
    2. Broken entries — manifest entries whose JSON file is missing.
    3. Orphaned files — JSON files on disk not referenced by the manifest.

    The oldest (baseline) and newest (latest) snapshots are always kept.

    Example:
        tscodekg snapshot prune --dry-run
        tscodekg snapshot prune
    """
    from tscode_kg.snapshots import SnapshotManager  # pylint: disable=import-outside-toplevel

    mgr = SnapshotManager(_default_snapshots_dir(snapshots_dir))
    result = mgr.prune_snapshots(dry_run=dry_run)

    prefix = "[dry-run] " if dry_run else ""
    if result.total_cleaned == 0:
        click.echo("Nothing to prune.")
        return

    if result.removed:
        click.echo(f"{prefix}Metric-duplicates removed: {len(result.removed)}")
        for key in result.removed:
            click.echo(f"  - {key}")
    if result.broken_entries:
        click.echo(f"{prefix}Broken manifest entries removed: {len(result.broken_entries)}")
        for key in result.broken_entries:
            click.echo(f"  - {key}")
    if result.orphaned_files:
        click.echo(f"{prefix}Orphaned JSON files removed: {len(result.orphaned_files)}")
        for fname in result.orphaned_files:
            click.echo(f"  - {fname}")

    action = "would be" if dry_run else "were"
    click.echo(f"\nTotal: {result.total_cleaned} item(s) {action} cleaned.")
