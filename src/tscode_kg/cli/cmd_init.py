"""
cli/cmd_init.py — tscodekg init command.

  init — download model, build graph, install hooks, capture snapshot
"""

from __future__ import annotations

import stat
import subprocess
import time
import tomllib
from pathlib import Path

import click

from tscode_kg.cli.cmd_hooks import _PRE_COMMIT_HOOK


def _has_tscodekg_config(repo_root: Path) -> bool:
    """Check whether pyproject.toml already has a [tool.tscodekg] section.

    :param repo_root: Repository root directory.
    :return: True when the section exists.
    """
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return False
    try:
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        return "tscodekg" in data.get("tool", {})
    except (OSError, ValueError):
        return False


def _scaffold_tscodekg_config(repo_root: Path) -> bool:
    """Append a minimal [tool.tscodekg] section to pyproject.toml if missing.

    Detects the most likely source directory (``src``, ``lib``, or ``app``)
    and sets it as the include list.

    :param repo_root: Repository root directory.
    :return: True if the section was added, False if skipped.
    """
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return False

    candidates = ["src", "lib", "app"]
    include_dirs: list[str] = [d for d in candidates if (repo_root / d).is_dir()]

    lines = [
        "",
        "[tool.tscodekg]",
        "# Directories to include in the knowledge graph build and analysis.",
        "# When unset, all directories are indexed.",
    ]
    if include_dirs:
        include_str = ", ".join(f'"{d}"' for d in include_dirs)
        lines.append(f"include = [{include_str}]")
    else:
        lines.append("# include = []")

    pyproject.open("a").write("\n".join(lines) + "\n")
    return True


@click.command("init")
@click.option(
    "--repo",
    default=".",
    type=click.Path(exists=True),
    show_default=True,
    help="Repository root.",
)
@click.option(
    "--model",
    default=None,
    help="SentenceTransformer model name (default: shared kg_utils default).",
)
@click.option("--skip-hooks", is_flag=True, help="Don't install the pre-commit git hook.")
@click.option("--skip-snapshot", is_flag=True, help="Don't capture an initial snapshot.")
@click.option("--force", is_flag=True, help="Overwrite existing graph data and hook.")
def init(
    repo: str,
    model: str | None,
    skip_hooks: bool,
    skip_snapshot: bool,
    force: bool,
) -> None:
    """Initialize TypeScriptKG in a repository.

    Downloads the embedding model, builds the knowledge graph (SQLite +
    sqlite-vec), optionally installs the pre-commit hook, and captures an
    initial snapshot.  Designed to be idempotent — safe to run more than once.

    Example::

        tscodekg init --repo .
    """
    from kg_utils.semantic import (  # pylint: disable=import-outside-toplevel
        DEFAULT_MODEL,
        _local_model_path,
    )

    from tscode_kg.kg import TypeScriptKG  # pylint: disable=import-outside-toplevel

    repo_root = Path(repo).resolve()
    model = model or DEFAULT_MODEL
    t_total = time.monotonic()

    click.echo()
    click.echo("  TypeScriptKG  Init")
    click.echo(f"  repo  {repo_root}")
    click.echo()

    # ------------------------------------------------------------------
    # Step 0: Scaffold [tool.tscodekg] in pyproject.toml if missing
    # ------------------------------------------------------------------
    if not _has_tscodekg_config(repo_root):
        if _scaffold_tscodekg_config(repo_root):
            click.echo("  [0/4]  Added [tool.tscodekg] section to pyproject.toml")
        else:
            click.echo("  [0/4]  No pyproject.toml found — skipping config scaffold")
    else:
        click.echo("  [0/4]  [tool.tscodekg] config already present")

    # ------------------------------------------------------------------
    # Step 1: Download the embedding model
    # ------------------------------------------------------------------
    click.echo()
    local_path = _local_model_path(model)

    if local_path.exists() and not force:
        click.echo(f"  [1/4]  Model already cached at {local_path}")
    else:
        click.echo(f"  [1/4]  Downloading embedding model '{model}'...")
        from sentence_transformers import (  # pylint: disable=import-outside-toplevel
            SentenceTransformer,
        )

        st_model = SentenceTransformer(model)
        local_path.mkdir(parents=True, exist_ok=True)
        st_model.save(str(local_path))
        click.echo(f"         OK: model saved to {local_path}")

    # ------------------------------------------------------------------
    # Step 2: Build the knowledge graph (full wipe)
    # ------------------------------------------------------------------
    click.echo()
    click.echo("  [2/4]  Building knowledge graph...")
    kg = TypeScriptKG(repo_root=repo_root, model=model)
    try:
        stats = kg.build(wipe=True)
        click.echo(f"         OK: {stats}")
    finally:
        kg.close()

    # ------------------------------------------------------------------
    # Step 3: Install pre-commit hook
    # ------------------------------------------------------------------
    click.echo()
    if skip_hooks:
        click.echo("  [3/4]  Skipping hook installation (--skip-hooks)")
    else:
        git_dir = repo_root / ".git"
        if not git_dir.is_dir():
            click.echo("  [3/4]  Not a git repository — skipping hook installation")
        else:
            hooks_dir = git_dir / "hooks"
            hooks_dir.mkdir(exist_ok=True)
            hook_path = hooks_dir / "pre-commit"

            if hook_path.exists() and not force:
                click.echo(f"  [3/4]  Hook already exists: {hook_path}")
                click.echo("         Use --force to overwrite.")
            else:
                hook_path.write_text(_PRE_COMMIT_HOOK)
                mode = hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
                hook_path.chmod(mode)
                click.echo(f"  [3/4]  OK: installed pre-commit hook at {hook_path}")

    # ------------------------------------------------------------------
    # Step 4: Capture initial snapshot
    # ------------------------------------------------------------------
    click.echo()
    if skip_snapshot:
        click.echo("  [4/4]  Skipping initial snapshot (--skip-snapshot)")
    else:
        try:
            tree_hash = (
                subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(repo_root),
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
            branch = (
                subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=str(repo_root),
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            tree_hash = ""
            branch = None

        from tscode_kg.cli.cmd_snapshot import (  # pylint: disable=import-outside-toplevel
            save_snapshot,
        )

        try:
            save_snapshot.callback(
                version="",
                repo=str(repo_root),
                db=None,
                snapshots_dir=None,
                branch=branch,
                tree_hash=tree_hash,
            )
            click.echo("  [4/4]  OK: initial snapshot captured")
        except Exception as exc:  # noqa: BLE001
            click.echo(f"  [4/4]  Snapshot skipped: {exc}")

    elapsed = time.monotonic() - t_total
    click.echo()
    click.echo(f"  Done in {elapsed:.1f}s — TypeScriptKG is ready.")
    click.echo('  Try:  tscodekg query "authentication middleware"')
