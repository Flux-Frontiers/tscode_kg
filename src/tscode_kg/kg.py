#!/usr/bin/env python3
"""
kg.py — TypeScriptKG: concrete KGModule for TypeScript/JavaScript codebases.

Owns the TS/JS-specific extraction layer (tree-sitter AST) and delegates all
generic infrastructure (SQLite, LanceDB, hybrid query, snippet packing,
snapshots) to the KGModule base class from kg_utils.pipeline.

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

from pathlib import Path

try:
    from kg_utils.extractor import KGExtractor
    from kg_utils.pipeline import KGModule
    from kg_utils.semantic import DEFAULT_MODEL
    from kg_utils.specs import BuildStats, QueryResult, SnippetPack
    from kg_utils.store import GraphStore  # noqa: F401
except ImportError as _e:
    raise ImportError(
        "TypeScriptKG requires kgmodule-utils[semantic] for its graph infrastructure.\n"
        "Install with:  pip install 'tscode-kg[kg]'\n"
        f"Original error: {_e}"
    ) from _e

from tscode_kg.config import load_exclude_dirs, load_include_dirs
from tscode_kg.extractor import TSCodeExtractor

__all__ = [
    "TypeScriptKG",
    "BuildStats",
    "QueryResult",
    "SnippetPack",
]

# TypeScript/JavaScript node kind priority for ranking
_TS_KIND_PRIORITY: dict[str, int] = {
    "function": 0,
    "method": 1,
    "class": 2,
    "interface": 3,
    "type_alias": 4,
    "enum": 5,
    "namespace": 6,
    "module": 7,
    "symbol": 8,
}


class TypeScriptKG(KGModule):
    """
    Top-level orchestrator for the TypeScript/JavaScript Knowledge Graph.

    Subclasses :class:`~kg_utils.pipeline.KGModule` and provides the
    TypeScript/JS-specific extraction layer via :class:`~tscode_kg.extractor.TSCodeExtractor`.
    All generic infrastructure — SQLite persistence, LanceDB indexing,
    hybrid query, snippet packing — is inherited from KGModule.

    Typical usage::

        kg = TypeScriptKG(repo_root="/path/to/ts-repo")
        stats = kg.build(wipe=True)
        print(stats)

        result = kg.query("authentication middleware", k=8)
        pack = kg.pack("API error handling")
        pack.save("context.md")

    :param repo_root: Repository root directory.
    :param db_path: SQLite database path (defaults to ``<repo_root>/.tscodekg/graph.sqlite``).
    :param lancedb_dir: LanceDB directory (defaults to ``<repo_root>/.tscodekg/lancedb``).
    :param model: Sentence-transformer model name.
    :param table: LanceDB table name.
    """

    _default_dir = ".tscodekg"

    def __init__(
        self,
        repo_root: str | Path,
        db_path: str | Path | None = None,
        lancedb_dir: str | Path | None = None,
        *,
        model: str = DEFAULT_MODEL,
        table: str = "tscodekg_nodes",
    ) -> None:
        super().__init__(
            repo_root,
            db_path=db_path,
            lancedb_dir=lancedb_dir,
            model=model,
            table=table,
        )

    # ------------------------------------------------------------------
    # KGModule abstract interface
    # ------------------------------------------------------------------

    def make_extractor(self) -> KGExtractor:
        include = load_include_dirs(self.repo_root)
        exclude = load_exclude_dirs(self.repo_root)
        return TSCodeExtractor(self.repo_root, include=include, exclude=exclude)

    def kind(self) -> str:
        return "code"

    def analyze(self) -> str:
        """Run thorough structural analysis and return a Markdown report.

        Uses :class:`~tscode_kg.analysis.TSCodeKGAnalyzer` for a full 14-phase
        analysis (fan-in, fan-out, module coupling, JSDoc coverage, hierarchy, …).
        Falls back to a lightweight summary when the KG has not been built yet.
        """
        try:
            from tscode_kg.analysis import TSCodeKGAnalyzer  # noqa: PLC0415

            analyzer = TSCodeKGAnalyzer(self)
            analyzer.run_analysis()
            return analyzer.to_markdown()
        except Exception as exc:  # noqa: BLE001
            try:
                return _render_analysis(str(self.repo_root), self.store.stats())
            except Exception:  # noqa: BLE001
                return f"# TypeScriptKG Analysis\n\nAnalysis failed: {exc}\n"

    # ------------------------------------------------------------------
    # TS-specific overrides
    # ------------------------------------------------------------------

    def _kind_priority(self, kind: str) -> int:
        return _TS_KIND_PRIORITY.get(kind, 99)

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"TypeScriptKG(repo_root={self.repo_root!r}, "
            f"db_path={self.db_path!r}, "
            f"lancedb_dir={self.lancedb_dir!r}, "
            f"model={self.model_name!r})"
        )


# ---------------------------------------------------------------------------
# Analysis renderer
# ---------------------------------------------------------------------------


def _render_analysis(repo_root: str, stats: dict) -> str:
    """Render a Markdown analysis report from store stats."""
    lines: list[str] = [
        "# TypeScriptKG Analysis Report\n",
        f"**Repository:** `{repo_root}`\n",
        "---\n",
        "## Structural Metrics\n",
        f"- **Total nodes:** {stats.get('total_nodes', 0):,}",
        f"- **Meaningful nodes:** {stats.get('meaningful_nodes', 0):,}",
        f"- **Total edges:** {stats.get('total_edges', 0):,}",
    ]

    cov = stats.get("docstring_coverage")
    if cov is not None:
        lines.append(f"- **JSDoc coverage:** {cov:.1%} *(functions + methods)*")

    node_counts: dict = stats.get("node_counts", {})
    if node_counts:
        lines.append("\n### Nodes by Kind\n")
        lines.append("| Kind | Count |")
        lines.append("|------|------:|")
        for kind, count in sorted(node_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| {kind} | {count:,} |")

    edge_counts: dict = stats.get("edge_counts", {})
    if edge_counts:
        lines.append("\n### Edges by Relation\n")
        lines.append("| Relation | Count |")
        lines.append("|----------|------:|")
        for rel, count in sorted(edge_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| {rel} | {count:,} |")

    lines.append("\n---\n")
    lines.append(
        "> Graph built by deterministic tree-sitter AST extraction. "
        "No LLM inference used in indexing."
    )
    return "\n".join(lines)
