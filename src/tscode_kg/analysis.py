#!/usr/bin/env python3
"""
TSCodeKG Thorough Repository Analysis Tool

Performs comprehensive architectural analysis of TypeScript/JavaScript repositories
using TypeScriptKG's graph traversal capabilities. Analyzes:
- Complexity hotspots (highest fan-in/fan-out functions and methods)
- Architectural patterns (core modules, integration points)
- Dependency analysis (orphaned declarations, tight coupling)
- JSDoc coverage (determines semantic retrieval quality)
- Inheritance, implements, and interface-extends hierarchies
- Exported public API surface

Operational behaviour:
- Entry point defaults: resolves ``repo_root`` and defaults ``db_path``/``vectors_path``
  to ``.tscodekg/graph.sqlite`` and ``.tscodekg/vectors.sqlite``.
- Logging: Rich console for user-facing status; ``logging`` for diagnostics.
- Error handling: degrades gracefully when optional data is missing.

Usage (Python API):
    from tscode_kg import TypeScriptKG
    from tscode_kg.analysis import TSCodeKGAnalyzer

    kg = TypeScriptKG("/path/to/ts-repo")
    kg.build()
    analyzer = TSCodeKGAnalyzer(kg)
    results = analyzer.run_analysis(report_path="analysis.md")

Usage (CLI):
    tscodekg analyze /path/to/ts-repo [--report analysis.md]
"""

from __future__ import annotations

import datetime
import logging
import os
import platform
import subprocess
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from rich.console import Console

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class FunctionMetrics:
    """Metrics for a single function, method, or class.

    :param node_id: Stable node identifier
    :param name: Function/class name
    :param module: Module path containing this definition
    :param kind: Node kind (function, method, class, interface)
    :param fan_in: Count of callers (how many call this)
    :param fan_out: Count of callees (how many this calls)
    :param lines: Approximate line count
    :param docstring: JSDoc text if available
    """

    node_id: str
    name: str
    module: str
    kind: str
    fan_in: int
    fan_out: int
    lines: int
    docstring: str | None = None


@dataclass
class ModuleMetrics:
    """Metrics for a module (single TypeScript/JavaScript file).

    :param path: Module file path (relative to repo root)
    :param functions: Count of top-level functions defined
    :param classes: Count of classes defined
    :param methods: Count of methods defined
    :param incoming_deps: Modules whose code calls into this one
    :param outgoing_deps: Modules this one imports from
    :param total_fan_in: Sum of cross-module callers for all nodes in module
    :param cohesion_score: Internal coupling strength (0–1)
    """

    path: str
    functions: int
    classes: int
    methods: int
    incoming_deps: list[str]
    outgoing_deps: list[str]
    total_fan_in: int
    cohesion_score: float


@dataclass
class CallChain:
    """Represents a notable call chain.

    :param chain: List of function/method names in call order
    :param depth: Length of the chain
    :param total_callers: Sum of all callers in chain
    """

    chain: list[str]
    depth: int
    total_callers: int


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class TSCodeKGAnalyzer:
    """Thorough TypeScript/JavaScript repository analyzer using TypeScriptKG.

    :param kg: TypeScriptKG instance (built KG required for useful results)
    :param console: Rich console for terminal output (creates new if None)
    :param snapshot_mgr: Optional SnapshotManager for temporal history
    :param include_dirs: Directories included in the indexed build
    :param exclude_dirs: Directories excluded from the indexed build
    """

    _TOTAL_PHASES = 14

    def __init__(
        self,
        kg,
        console: Console | None = None,
        snapshot_mgr=None,
        include_dirs: set[str] | None = None,
        exclude_dirs: set[str] | None = None,
    ) -> None:
        self.kg = kg
        self.console = console or Console()
        self.snapshot_mgr = snapshot_mgr
        self.include_dirs: set[str] = include_dirs or set()
        self.exclude_dirs: set[str] = exclude_dirs or set()

        # Phase results
        self.stats: dict = {}
        self.function_metrics: dict[str, FunctionMetrics] = {}
        self.module_metrics: dict[str, ModuleMetrics] = {}
        self.orphaned_functions: list[FunctionMetrics] = []
        self.high_fanout_functions: list[FunctionMetrics] = []
        self.critical_paths: list[CallChain] = []
        self.public_apis: list[FunctionMetrics] = []
        self.issues: list[str] = []
        self.strengths: list[str] = []
        self.jsdoc_coverage: dict = {}
        self.inheritance_analysis: dict = {}
        self.snapshot_history: list[dict] = []
        self.centrality_records: list = []
        self.centrality_modules: list[dict] = []
        self.coderank_scores: dict[str, float] = {}
        self.coderank_top_nodes: list[dict] = []
        self.concern_analysis: list[dict] = []
        self._phase_result: str = ""

    # ------------------------------------------------------------------
    # Phase runner
    # ------------------------------------------------------------------

    def _run_phase(self, num: int, name: str, fn: Callable[[], None]) -> None:
        self._phase_result = ""
        t0 = time.monotonic()
        fn()
        elapsed = time.monotonic() - t0
        result = f"  {self._phase_result}" if self._phase_result else ""
        self.console.print(
            f"  [cyan]▶ Phase {num:2d}/{self._TOTAL_PHASES}:[/cyan]"
            f" {name}{result}  [green]({elapsed:.1f}s)[/green]"
        )

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------

    def run_analysis(
        self,
        report_path: str | None = None,
        *,
        persist_centrality: bool = False,
    ) -> dict:
        """Run complete multi-phase analysis.

        Phase order:
        1.  Baseline metrics
        2.  CodeRank (global PageRank over CALLS + IMPORTS + INHERITS)
        3.  Fan-in analysis (most-called functions/methods)
        4.  Fan-out analysis (orchestrators)
        5.  Orphan detection (zero-callers excluding framework entry points)
        6.  Pattern detection
        7.  Module coupling (IMPORTS + cross-module CALLS)
        8.  Critical call chains
        9.  Public API surface (exported declarations)
        10. JSDoc coverage
        11. Class/interface hierarchy (INHERITS + IMPLEMENTS + EXTENDS)
        12. Generate insights and recommendations
        13. Snapshot history
        14. Structural centrality (SIR PageRank)

        :param report_path: Optional file path to write the Markdown report
        :param persist_centrality: When True, write centrality scores to SQLite
        :return: Dictionary of all analysis results
        """
        _start = datetime.datetime.now(datetime.UTC)
        try:
            self._run_phase(1, "Baseline metrics", self._analyze_baseline)
            self._run_phase(2, "CodeRank (global PageRank)", self._compute_coderank)
            self._run_phase(3, "Fan-in analysis", self._analyze_fan_in)
            self._run_phase(4, "Fan-out analysis", self._analyze_fan_out)
            self._run_phase(5, "Orphan detection", self._analyze_orphans)
            self._run_phase(6, "Pattern detection", self._detect_patterns)
            self._run_phase(7, "Module coupling", self._analyze_module_coupling)
            self._run_phase(8, "Critical call chains", self._analyze_critical_paths)
            self._run_phase(9, "Public API surface", self._identify_public_apis)
            self._run_phase(10, "JSDoc coverage", self._analyze_jsdoc_coverage)
            self._run_phase(11, "Class/interface hierarchy", self._analyze_inheritance)
            self._run_phase(12, "Generate insights", self._generate_insights)
            self._run_phase(13, "Snapshot history", self._analyze_snapshots)
            self._run_phase(14, "Structural centrality (SIR)", self._analyze_centrality)

            if persist_centrality and self.centrality_records:
                try:
                    from pycode_kg.analysis.centrality import (
                        StructuralImportanceRanker,  # noqa: PLC0415
                    )

                    StructuralImportanceRanker(self.kg.db_path).write_scores(
                        self.centrality_records
                    )
                except (ImportError, AttributeError, ValueError, RuntimeError):
                    pass

            if report_path:
                elapsed = (datetime.datetime.now(datetime.UTC) - _start).total_seconds()
                self._write_report(report_path, elapsed_seconds=elapsed)

            return self._compile_results()

        except (AttributeError, ValueError, RuntimeError) as exc:
            self.console.print(f"[red]Analysis failed: {exc}[/red]")
            logger.exception("Analysis failed")
            raise

    # ------------------------------------------------------------------
    # Phase implementations
    # ------------------------------------------------------------------

    def _analyze_baseline(self) -> None:
        """Phase 1: Establish baseline node and edge counts."""
        try:
            self.stats = self.kg.stats()
            n = self.stats.get("total_nodes", "?")
            e = self.stats.get("total_edges", "?")
            self._phase_result = f"nodes={n}  edges={e}"
        except (AttributeError, ValueError, RuntimeError) as exc:
            logger.warning("Could not get baseline stats: %s", exc)

    def _compute_coderank(self) -> None:
        """Phase 2: Compute global CodeRank (weighted PageRank) over the graph."""
        try:
            from pycode_kg.ranking.coderank import (  # noqa: PLC0415
                build_code_graph,
                compute_coderank,
            )

            graph = build_code_graph(
                str(self.kg.db_path),
                include_relations=("CALLS", "IMPORTS", "INHERITS"),
                exclude_test_paths=True,
            )
            self.coderank_scores = compute_coderank(graph)

            sorted_nodes = sorted(self.coderank_scores.items(), key=lambda kv: kv[1], reverse=True)
            top_nodes: list[dict] = []
            for node_id, score in sorted_nodes:
                if node_id.startswith("sym:"):
                    continue
                attrs = graph.nodes.get(node_id, {})
                kind = attrs.get("kind", "")
                if kind not in ("function", "method", "class", "module"):
                    continue
                top_nodes.append(
                    {
                        "node_id": node_id,
                        "score": score,
                        "kind": kind,
                        "name": attrs.get("name", node_id.split(":")[-1]),
                        "qualname": attrs.get("qualname", ""),
                        "module_path": attrs.get("module_path", ""),
                    }
                )
                if len(top_nodes) >= 25:
                    break

            self.coderank_top_nodes = top_nodes
            if top_nodes:
                self._phase_result = (
                    f"{len(self.coderank_scores)} nodes  top=`{top_nodes[0]['name']}`"
                )
            else:
                self._phase_result = f"{len(self.coderank_scores)} nodes"

        except (AttributeError, ValueError, RuntimeError, ImportError) as exc:
            logger.warning("CodeRank incomplete: %s", exc)
            self.console.print(f"[yellow]WARN[/yellow] CodeRank incomplete: {exc}")

    def _analyze_fan_in(self) -> None:
        """Phase 3: Find most-called functions and methods (fan-in).

        Seeds from CodeRank top nodes when available; falls back to a direct
        SQL scan when CodeRank is not installed.
        """
        try:
            con = self.kg.store.con
            if self.coderank_scores:
                rows = con.execute(
                    """
                    SELECT id, name, kind, module_path, docstring, lineno, end_lineno
                    FROM nodes
                    WHERE kind IN ('function', 'method', 'class')
                      AND id NOT LIKE 'sym:%'
                    ORDER BY module_path, name
                    """
                ).fetchall()
                scored: list[tuple[float, tuple]] = []
                for row in rows:
                    node_id = row[0]
                    score = self.coderank_scores.get(node_id, 0.0)
                    scored.append((score, row))
                scored.sort(key=lambda x: x[0], reverse=True)
                candidates = [row for _, row in scored[:100]]
                seed_label = "CodeRank-seeded"
            else:
                candidates = con.execute(
                    """
                    SELECT id, name, kind, module_path, docstring, lineno, end_lineno
                    FROM nodes
                    WHERE kind IN ('function', 'method', 'class')
                      AND id NOT LIKE 'sym:%'
                    ORDER BY module_path, name
                    """
                ).fetchall()
                seed_label = "SQL fallback"

            fan_in_data: list[tuple] = []
            for row in candidates:
                node_id, name, kind, module_path, docstring, lineno, end_lineno = row
                try:
                    caller_list = self.kg.callers(node_id, rel="CALLS")
                    fan_in_data.append(
                        (
                            node_id,
                            FunctionMetrics(
                                node_id=node_id,
                                name=name or "unknown",
                                module=module_path or "unknown",
                                kind=kind or "unknown",
                                fan_in=len(caller_list),
                                fan_out=0,
                                lines=max(0, (end_lineno or 0) - (lineno or 0)),
                                docstring=docstring,
                            ),
                        )
                    )
                except (AttributeError, ValueError, RuntimeError, TypeError):
                    pass

            fan_in_data.sort(key=lambda x: x[1].fan_in, reverse=True)
            for node_id, metrics in fan_in_data[:15]:
                self.function_metrics[node_id] = metrics

            self._phase_result = f"top {len(self.function_metrics)} by fan-in ({seed_label})"

        except (AttributeError, ValueError, RuntimeError) as exc:
            logger.warning("Fan-in analysis incomplete: %s", exc)
            self.console.print(f"[yellow]WARN[/yellow] Fan-in analysis incomplete: {exc}")

    def _analyze_fan_out(self) -> None:
        """Phase 4: Compute fan-out for identified nodes and find orchestrators."""
        try:
            for node_id, metrics in self.function_metrics.items():
                try:
                    edges = self.kg.store.edges_from(node_id, rel="CALLS", limit=200)
                    metrics.fan_out = len(edges) if edges else 0
                except (AttributeError, ValueError, RuntimeError):
                    pass

            # Find additional orchestrators not already in function_metrics
            try:
                result = self.kg.query(
                    "coordinator orchestrator manager setup initializer",
                    k=20,
                    hop=0,
                    rels=("CONTAINS",),
                )
                for node in result.nodes:
                    node_id = node.get("id")
                    if not node_id or node_id in self.function_metrics:
                        continue
                    if node.get("kind") not in ("function", "method"):
                        continue
                    try:
                        edges = self.kg.store.edges_from(node_id, rel="CALLS", limit=200)
                        fanout_count = len(edges) if edges else 0
                    except (AttributeError, ValueError, RuntimeError):
                        fanout_count = 0
                    if fanout_count > 20:
                        self.high_fanout_functions.append(
                            FunctionMetrics(
                                node_id=node_id,
                                name=node.get("name", "unknown"),
                                module=node.get("module_path", "unknown"),
                                kind=node.get("kind", "unknown"),
                                fan_in=0,
                                fan_out=fanout_count,
                                lines=max(
                                    0,
                                    (node.get("end_lineno") or 0) - (node.get("lineno") or 0),
                                ),
                            )
                        )
            except (AttributeError, ValueError, RuntimeError):
                pass

            self._phase_result = f"{len(self.high_fanout_functions)} high-fanout functions"

        except (AttributeError, ValueError, RuntimeError) as exc:
            logger.warning("Fan-out analysis incomplete: %s", exc)

    def _is_ts_entry_point(self, node: dict) -> bool:
        """Return True if this node is a framework-driven entry point.

        TypeScript entry points that have zero internal callers by design:
        - MCP tool functions (in mcp_server files)
        - CLI command handlers (in cli/ directories or *cli.ts files)
        - Next.js page/API route exports (files under pages/ or app/)
        - Express/Fastify route handlers registered directly on app
        - Event listener callbacks (named handle*, on*, listen*)
        - Constructor functions (named with leading capital, kind=class)
        """
        name = node.get("name", "")
        module = node.get("module_path", "") or ""
        kind = node.get("kind", "")

        if "mcp_server" in module or "mcp-server" in module:
            return True
        if "/cli/" in module or module.endswith("cli.ts") or module.endswith("cli.js"):
            return True
        if "/pages/" in module or "/app/" in module or "/routes/" in module:
            return True
        if name.startswith(("on", "handle", "listen")) and kind in ("function", "method"):
            return True
        if kind == "class":
            return True

        return False

    def _analyze_orphans(self) -> None:
        """Phase 5: Detect orphaned declarations (zero callers, not entry points)."""
        try:
            con = self.kg.store.con
            rows = con.execute(
                """
                SELECT id, name, kind, module_path, docstring, lineno, end_lineno
                FROM nodes
                WHERE kind IN ('function', 'method')
                  AND id NOT LIKE 'sym:%'
                ORDER BY module_path, name
                """
            ).fetchall()

            for node_id, name, kind, module_path, docstring, lineno, end_lineno in rows:
                try:
                    callers = self.kg.callers(node_id, rel="CALLS")
                    if callers:
                        continue
                    node = {
                        "id": node_id,
                        "name": name,
                        "kind": kind,
                        "module_path": module_path,
                    }
                    if self._is_ts_entry_point(node):
                        continue
                    self.orphaned_functions.append(
                        FunctionMetrics(
                            node_id=node_id,
                            name=name or "unknown",
                            module=module_path or "unknown",
                            kind=kind or "unknown",
                            fan_in=0,
                            fan_out=0,
                            lines=max(0, (end_lineno or 0) - (lineno or 0)),
                            docstring=docstring,
                        )
                    )
                except (AttributeError, ValueError, RuntimeError, TypeError):
                    pass

            self._phase_result = f"{len(self.orphaned_functions)} orphaned declarations"

        except (AttributeError, ValueError, RuntimeError) as exc:
            logger.warning("Orphan detection incomplete: %s", exc)

    def _detect_patterns(self) -> None:
        """Phase 6: Detect core modules and architectural coupling patterns."""
        try:
            module_call_counts: dict[str, int] = defaultdict(int)
            for metrics in self.function_metrics.values():
                mod = metrics.module.split("/")[0] if "/" in metrics.module else metrics.module
                module_call_counts[mod] += metrics.fan_in

            core_modules = sorted(module_call_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            if core_modules:
                self._phase_result = f"{len(core_modules)} core modules"

            high_fanout = sorted(
                list(self.function_metrics.values()) + self.high_fanout_functions,
                key=lambda m: m.fan_out,
                reverse=True,
            )[:10]
            for func in high_fanout:
                if func.fan_out > 40:
                    self.issues.append(
                        f"[HIGH] `{func.name}` has high fan-out ({func.fan_out} callees) "
                        "— consider decomposing into smaller, focused functions"
                    )
        except (AttributeError, ValueError, RuntimeError) as exc:
            logger.warning("Pattern detection incomplete: %s", exc)

    def _analyze_module_coupling(self) -> None:
        """Phase 7: Compute module-level coupling using IMPORTS and cross-module CALLS.

        Outgoing deps = modules/packages this module imports.
        Incoming deps = modules whose functions call into this one.
        Cohesion = incoming / (incoming + outgoing + 1).
        """
        try:
            con = self.kg.store.con

            module_rows = con.execute(
                "SELECT id, module_path FROM nodes WHERE kind = 'module' ORDER BY module_path"
            ).fetchall()

            # Cross-module CALLS: src.module_path → dst.module_path
            cross_call_pairs = con.execute(
                """
                SELECT DISTINCT src.module_path AS caller_mod, dst.module_path AS callee_mod
                FROM edges e
                JOIN nodes src ON e.src = src.id
                JOIN nodes dst ON e.dst = dst.id
                WHERE e.rel = 'CALLS'
                  AND src.module_path IS NOT NULL
                  AND dst.module_path IS NOT NULL
                  AND src.module_path != dst.module_path
                """
            ).fetchall()

            # IMPORTS: count outgoing imports per module
            import_rows = con.execute(
                """
                SELECT src.module_path, COUNT(*) AS import_count
                FROM edges e
                JOIN nodes src ON e.src = src.id
                WHERE e.rel = 'IMPORTS'
                  AND src.kind = 'module'
                  AND src.module_path IS NOT NULL
                GROUP BY src.module_path
                """
            ).fetchall()
            import_count_by_mod: dict[str, int] = {r[0]: r[1] for r in import_rows}

            # Build cross-call maps
            cross_incoming: dict[str, set[str]] = defaultdict(set)  # callee_mod → callers
            cross_outgoing: dict[str, set[str]] = defaultdict(set)  # caller_mod → callees
            for caller_mod, callee_mod in cross_call_pairs:
                if caller_mod and callee_mod:
                    cross_incoming[callee_mod].add(caller_mod)
                    cross_outgoing[caller_mod].add(callee_mod)

            # Node counts per module
            count_rows = con.execute(
                "SELECT module_path, kind, COUNT(*) FROM nodes"
                " WHERE kind IN ('function', 'class', 'method')"
                " GROUP BY module_path, kind"
            ).fetchall()
            kind_counts: dict[str, dict[str, int]] = defaultdict(dict)
            for mod_path, kind, cnt in count_rows:
                if mod_path:
                    kind_counts[mod_path][kind] = cnt

            for _, module_path in module_rows:
                module_path = module_path or "unknown"
                incoming = list(cross_incoming.get(module_path, set()))
                outgoing = list(cross_outgoing.get(module_path, set()))
                # Supplement outgoing with import count if no cross-call data
                n_imports = import_count_by_mod.get(module_path, 0)
                effective_outgoing = max(len(outgoing), min(n_imports, 10))
                cohesion = min(1.0, len(incoming) / (len(incoming) + effective_outgoing + 1))
                counts = kind_counts.get(module_path, {})
                self.module_metrics[module_path] = ModuleMetrics(
                    path=module_path,
                    functions=counts.get("function", 0),
                    classes=counts.get("class", 0),
                    methods=counts.get("method", 0),
                    incoming_deps=incoming,
                    outgoing_deps=outgoing,
                    total_fan_in=len(incoming),
                    cohesion_score=cohesion,
                )

            self._phase_result = f"{len(self.module_metrics)} modules"

        except (AttributeError, ValueError, RuntimeError) as exc:
            logger.warning("Module coupling analysis incomplete: %s", exc)

    def _analyze_critical_paths(self) -> None:
        """Phase 8: Trace key call chains starting from high fan-in nodes."""
        try:
            top_functions = [
                m
                for m in sorted(
                    self.function_metrics.values(), key=lambda m: m.fan_in, reverse=True
                )
            ][:5]

            for func in top_functions:
                try:
                    callers = self.kg.callers(func.node_id, rel="CALLS")
                    chain_names = [func.name]
                    chain_modules = [func.module]
                    seen_ids: set[str] = {func.node_id}
                    current_id = func.node_id

                    for _ in range(6):
                        edges = self.kg.store.edges_from(current_id, rel="CALLS", limit=5)
                        callee = None
                        for edge in edges:
                            dst_id = edge["dst"]
                            if dst_id in seen_ids or dst_id.startswith("sym:"):
                                continue
                            node = self.kg.store.node(dst_id)
                            if node and node.get("module_path"):
                                callee = node
                                seen_ids.add(dst_id)
                                current_id = dst_id
                                break
                        if callee:
                            chain_names.append(callee.get("name", "?"))
                            chain_modules.append(callee.get("module_path", ""))
                        else:
                            break

                    if callers:
                        chain_names = [callers[0].get("name", "?"), *chain_names]
                        chain_modules = [callers[0].get("module_path", ""), *chain_modules]

                    crosses_module = len(set(chain_modules)) > 1
                    if len(chain_names) >= 4 or crosses_module:
                        self.critical_paths.append(
                            CallChain(
                                chain=chain_names,
                                depth=len(chain_names),
                                total_callers=len(callers),
                            )
                        )
                except (AttributeError, ValueError, RuntimeError):
                    pass

            self._phase_result = f"{len(self.critical_paths)} key call chains"

        except (AttributeError, ValueError, RuntimeError) as exc:
            logger.warning("Call chain analysis incomplete: %s", exc)

    def _identify_public_apis(self) -> None:
        """Phase 9: Identify exported public API declarations.

        Strategy (priority order):
        1. Scan source files for ``export`` keyword before function/class/interface/
           type/const declarations and look those names up in the graph.
        2. Supplement with non-private functions in function_metrics that have
           at least one cross-module caller.
        """
        try:
            already_ids: set[str] = set()
            repo_root = Path(self.kg.repo_root)
            con = self.kg.store.con

            # Step 1: grep source files for top-level exports
            _TS_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mts", ".cts", ".mjs", ".cjs"}
            _SKIP = {"node_modules", ".git", "dist", "build", ".next", ".tscodekg"}

            export_names: set[str] = set()
            for source_file in repo_root.rglob("*"):
                if not source_file.is_file():
                    continue
                if source_file.suffix not in _TS_EXTS:
                    continue
                if any(part in _SKIP for part in source_file.parts):
                    continue
                try:
                    text = source_file.read_text(encoding="utf-8", errors="replace")
                    for line in text.splitlines():
                        stripped = line.strip()
                        if not stripped.startswith("export"):
                            continue
                        # export function foo / export class Foo / export const foo
                        # export interface Foo / export type Foo / export enum Foo
                        # export default function foo / export default class Foo
                        tokens = stripped.split()
                        for i, tok in enumerate(tokens):
                            if tok in (
                                "function",
                                "class",
                                "interface",
                                "type",
                                "enum",
                                "const",
                                "let",
                                "var",
                            ):
                                if i + 1 < len(tokens):
                                    candidate = tokens[i + 1].rstrip("(<{:=")
                                    if (
                                        candidate
                                        and candidate[0].isalpha()
                                        or candidate.startswith("_")
                                    ):
                                        export_names.add(candidate)
                                break
                except OSError:
                    pass

            for name in export_names:
                rows = con.execute(
                    """
                    SELECT id, name, kind, module_path, docstring
                    FROM nodes
                    WHERE name = ?
                      AND kind IN ('function', 'method', 'class', 'interface', 'type_alias', 'enum')
                      AND id NOT LIKE 'sym:%'
                    """,
                    (name,),
                ).fetchall()
                for node_id, nm, kind, module_path, docstring in rows:
                    if node_id in already_ids:
                        continue
                    try:
                        fan_in = len(self.kg.callers(node_id, rel="CALLS"))
                    except (AttributeError, ValueError, RuntimeError):
                        fan_in = 0
                    self.public_apis.append(
                        FunctionMetrics(
                            node_id=node_id,
                            name=nm or name,
                            module=module_path or "",
                            kind=kind,
                            fan_in=fan_in,
                            fan_out=0,
                            lines=0,
                            docstring=docstring,
                        )
                    )
                    already_ids.add(node_id)

            # Step 2: supplement from high fan-in function_metrics
            for func in sorted(
                self.function_metrics.values(), key=lambda m: m.fan_in, reverse=True
            ):
                if (
                    func.kind in ("function", "class")
                    and func.fan_in >= 1
                    and not func.name.startswith("_")
                    and func.node_id not in already_ids
                ):
                    self.public_apis.append(func)
                    already_ids.add(func.node_id)

            self.public_apis.sort(key=lambda m: m.fan_in, reverse=True)
            self._phase_result = f"{len(self.public_apis)} exported declarations"

        except (AttributeError, ValueError, RuntimeError) as exc:
            logger.warning("Public API identification incomplete: %s", exc)

    def _analyze_jsdoc_coverage(self) -> None:
        """Phase 10: Measure JSDoc coverage across all node kinds."""
        try:
            con = self.kg.store.con
            rows = con.execute(
                """
                SELECT
                    kind,
                    COUNT(*) AS total,
                    SUM(
                        CASE WHEN docstring IS NOT NULL AND TRIM(docstring) != ''
                        THEN 1 ELSE 0 END
                    ) AS with_doc
                FROM nodes
                WHERE kind IN ('function', 'method', 'class', 'interface', 'module')
                GROUP BY kind
                ORDER BY kind
                """
            ).fetchall()

            by_kind: dict[str, dict[str, int]] = {}
            overall_total = 0
            overall_with_doc = 0
            for kind, total, with_doc in rows:
                by_kind[kind] = {"total": total, "with_doc": with_doc}
                overall_total += total
                overall_with_doc += with_doc

            overall_pct = (overall_with_doc / overall_total * 100) if overall_total else 0.0
            self.jsdoc_coverage = {
                "by_kind": by_kind,
                "total": overall_total,
                "with_doc": overall_with_doc,
                "coverage_pct": round(overall_pct, 1),
            }
            self._phase_result = f"{overall_with_doc}/{overall_total} nodes ({overall_pct:.1f}%)"

        except (AttributeError, ValueError, RuntimeError) as exc:
            logger.warning("JSDoc coverage analysis incomplete: %s", exc)

    def _analyze_inheritance(self) -> None:
        """Phase 11: Analyze class and interface hierarchies.

        Processes three edge types:
        - INHERITS: class extends class
        - IMPLEMENTS: class implements interface
        - EXTENDS: interface extends interface
        """
        try:
            con = self.kg.store.con

            inherits_rows = con.execute(
                "SELECT src, dst FROM edges WHERE rel = 'INHERITS'"
            ).fetchall()
            implements_rows = con.execute(
                "SELECT src, dst FROM edges WHERE rel = 'IMPLEMENTS'"
            ).fetchall()
            extends_rows = con.execute(
                "SELECT src, dst FROM edges WHERE rel = 'EXTENDS'"
            ).fetchall()

            total_edges = len(inherits_rows) + len(implements_rows) + len(extends_rows)

            if total_edges == 0:
                self.inheritance_analysis = {
                    "total_inherits_edges": 0,
                    "total_implements_edges": 0,
                    "total_extends_edges": 0,
                    "classes": [],
                    "max_depth": 0,
                    "multiple_inheritance": [],
                    "implements": [],
                }
                self._phase_result = "no hierarchy edges"
                return

            parents: dict[str, set[str]] = {}
            children: dict[str, set[str]] = {}
            all_classes: set[str] = set()

            for src, dst in inherits_rows:
                if dst.startswith("sym:"):
                    continue
                parents.setdefault(src, set()).add(dst)
                children.setdefault(dst, set()).add(src)
                all_classes.add(src)
                all_classes.add(dst)

            def _compute_depth(cls_id: str, memo: dict[str, int]) -> int:
                if cls_id in memo:
                    return max(memo[cls_id], 0)
                ps = parents.get(cls_id, set())
                if not ps:
                    memo[cls_id] = 0
                    return 0
                memo[cls_id] = -1
                depth = 1 + max(_compute_depth(p, memo) for p in ps)
                memo[cls_id] = depth
                return depth

            depth_memo: dict[str, int] = {}
            class_data: list[dict] = []
            multiple_inheritance: list[dict] = []

            for cls_id in sorted(all_classes):
                node = self.kg.store.node(cls_id)
                name = node.get("name", cls_id.split(":")[-1]) if node else cls_id.split(":")[-1]
                module = node.get("module_path", "") if node else ""
                cls_parents = parents.get(cls_id, set())
                depth = _compute_depth(cls_id, depth_memo)
                class_data.append(
                    {
                        "node_id": cls_id,
                        "name": name,
                        "module": module,
                        "depth": depth,
                        "parent_count": len(cls_parents),
                        "child_count": len(children.get(cls_id, set())),
                    }
                )
                if len(cls_parents) > 1:
                    parent_names = []
                    for p in sorted(cls_parents):
                        pn = self.kg.store.node(p)
                        parent_names.append(pn.get("name", p) if pn else p.split(":")[-1])
                    multiple_inheritance.append(
                        {"class": name, "module": module, "bases": sorted(parent_names)}
                    )

            max_depth = max((e["depth"] for e in class_data), default=0)

            # Implements table
            implements_list: list[dict] = []
            for src, dst in implements_rows:
                src_node = self.kg.store.node(src)
                dst_node = self.kg.store.node(dst) if not dst.startswith("sym:") else None
                cls_name = src_node.get("name", src) if src_node else src.split(":")[-1]
                iface_name = dst_node.get("name", dst) if dst_node else dst.split(":")[-1]
                cls_mod = src_node.get("module_path", "") if src_node else ""
                implements_list.append(
                    {"class": cls_name, "interface": iface_name, "module": cls_mod}
                )

            self.inheritance_analysis = {
                "total_inherits_edges": len(inherits_rows),
                "total_implements_edges": len(implements_rows),
                "total_extends_edges": len(extends_rows),
                "classes": sorted(class_data, key=lambda x: x["depth"], reverse=True),
                "max_depth": max_depth,
                "multiple_inheritance": multiple_inheritance,
                "implements": implements_list,
            }

            self._phase_result = (
                f"{len(all_classes)} classes  max-depth={max_depth}  "
                f"{len(implements_rows)} implements  {len(extends_rows)} iface-extends"
            )

        except (AttributeError, ValueError, RuntimeError) as exc:
            logger.warning("Inheritance analysis incomplete: %s", exc)
            self.console.print(f"[yellow]WARN[/yellow] Inheritance analysis incomplete: {exc}")

    def _generate_insights(self) -> None:
        """Phase 12: Compile actionable insights from earlier phases."""
        if len(self.function_metrics) > 0:
            self.strengths.append(
                f"Well-structured codebase — {len(self.function_metrics)} core functions identified"
            )

        if len(self.orphaned_functions) == 0:
            self.strengths.append("No obvious dead code detected")
        else:
            names = ", ".join(f"`{f.name}`" for f in self.orphaned_functions[:5])
            suffix = (
                f" (and {len(self.orphaned_functions) - 5} more)"
                if len(self.orphaned_functions) > 5
                else ""
            )
            self.issues.append(
                f"[WARN] {len(self.orphaned_functions)} orphaned declarations: {names}{suffix} — "
                "zero callers detected; verify these aren't dead code"
            )

        if len(self.high_fanout_functions) == 0:
            self.strengths.append("No god functions detected — healthy fan-out distribution")
        else:
            self.issues.append(
                f"[WARN] {len(self.high_fanout_functions)} high fan-out functions — "
                "potential orchestrators or god objects"
            )

        # JSDoc coverage signals
        cov = self.jsdoc_coverage
        if cov:
            pct = cov["coverage_pct"]
            if pct >= 80:
                self.strengths.append(
                    f"Good JSDoc coverage: {pct}% of declarations documented — "
                    "semantic retrieval will be effective"
                )
            elif pct >= 50:
                self.issues.append(
                    f"[WARN] Moderate JSDoc coverage ({pct}%) — semantic retrieval is degraded "
                    "for undocumented nodes; prioritize high-fan-in functions first"
                )
            else:
                self.issues.append(
                    f"[LOW] Low JSDoc coverage ({pct}%) — semantic query quality will be poor; "
                    "undocumented nodes embed only identifiers, not natural language"
                )

        # Module size checks
        try:
            large_modules = self.kg.store.con.execute(
                """
                SELECT module_path, COUNT(*) AS cnt
                FROM nodes
                WHERE kind IN ('function', 'method', 'class')
                  AND module_path IS NOT NULL
                GROUP BY module_path
                HAVING cnt > 30
                ORDER BY cnt DESC
                LIMIT 5
                """
            ).fetchall()
            for mod_path, cnt in large_modules:
                mod_name = mod_path.split("/")[-1] if mod_path else "?"
                self.issues.append(
                    f"[WARN] `{mod_name}` has {cnt} declarations — "
                    "consider splitting into focused modules"
                )
        except (AttributeError, ValueError, RuntimeError):
            pass

        # Inheritance insights
        inh = self.inheritance_analysis
        if inh:
            if inh.get("max_depth", 0) > 4:
                self.issues.append(
                    f"[WARN] Deep inheritance hierarchy (max depth {inh['max_depth']}) — "
                    "prefer composition over deep inheritance in TypeScript"
                )
            elif inh.get("max_depth", 0) > 0:
                self.strengths.append(
                    f"Shallow inheritance hierarchy (max depth {inh['max_depth']}) — "
                    "composition-friendly design"
                )
            if inh.get("implements"):
                self.strengths.append(
                    f"{len(inh['implements'])} class/interface contracts via `implements` — "
                    "type-safe polymorphism in use"
                )

        # Centrality cross-reference
        if self.centrality_modules and self.module_metrics:
            sir_by_path = {m["module_path"]: m for m in self.centrality_modules[:10]}
            risky = [
                m
                for path, m in sir_by_path.items()
                if path in self.module_metrics
                and (
                    len(self.module_metrics[path].incoming_deps)
                    + len(self.module_metrics[path].outgoing_deps)
                )
                > 4
            ]
            if risky:
                names = ", ".join(f"`{m['module_path'].split('/')[-1]}`" for m in risky[:3])
                self.issues.append(
                    f"[WARN] High-SIR modules with tight coupling: {names} — "
                    "structurally central AND heavily connected; changes here ripple broadly"
                )

        self._phase_result = f"{len(self.issues)} issues  {len(self.strengths)} strengths"

    def _analyze_snapshots(self) -> None:
        """Phase 13: Load snapshot history for temporal comparison."""
        if self.snapshot_mgr is None:
            self._phase_result = "skipped (no snapshot manager)"
            return
        try:
            self.snapshot_history = self.snapshot_mgr.list_snapshots(limit=10)
            self._phase_result = f"{len(self.snapshot_history)} snapshot(s)"
        except (AttributeError, ValueError, RuntimeError, OSError) as exc:
            logger.warning("Snapshot history unavailable: %s", exc)

    def _analyze_centrality(self) -> None:
        """Phase 14: Compute Structural Importance Ranking (SIR) via PageRank."""
        try:
            from pycode_kg.analysis.centrality import (  # noqa: PLC0415
                StructuralImportanceRanker,
                aggregate_module_scores,
            )

            ranker = StructuralImportanceRanker(self.kg.db_path)
            all_records = ranker.compute()
            self.centrality_records = all_records[:25]
            self.centrality_modules = aggregate_module_scores(all_records)
            self._phase_result = f"{len(all_records)} nodes  {len(self.centrality_modules)} modules"
        except (AttributeError, ValueError, RuntimeError, ImportError) as exc:
            logger.warning("Centrality analysis incomplete: %s", exc)
            self.console.print(f"[yellow]WARN[/yellow] Centrality incomplete: {exc}")

    # ------------------------------------------------------------------
    # Report generation helpers
    # ------------------------------------------------------------------

    def _compute_quality_grade(self) -> tuple[float, str, str]:
        """Compute an overall quality score, letter grade, and label.

        Scoring (100 points):
        - JSDoc coverage (0–40 pts): ≥80% → 40, ≥50% → 20, else 0
        - Orphaned declarations (0–25 pts): 0 → 25, 1–2 → 15, 3–5 → 5, else 0
        - High fan-out functions (0–20 pts): 0 → 20, 1–2 → 12, else 4
        - Type safety signals (0–15 pts): implements edges present → 15, else 0
        """
        score = 0.0

        cov = self.jsdoc_coverage
        if cov:
            pct = cov.get("coverage_pct", 0)
            if pct >= 80:
                score += 40
            elif pct >= 50:
                score += 20

        n_orphaned = len(self.orphaned_functions)
        if n_orphaned == 0:
            score += 25
        elif n_orphaned <= 2:
            score += 15
        elif n_orphaned <= 5:
            score += 5

        n_fanout = len(self.high_fanout_functions)
        if n_fanout == 0:
            score += 20
        elif n_fanout <= 2:
            score += 12
        else:
            score += 4

        inh = self.inheritance_analysis
        if inh and inh.get("total_implements_edges", 0) > 0:
            score += 15

        if score >= 90:
            grade, label = "A", "Excellent"
        elif score >= 75:
            grade, label = "B", "Good"
        elif score >= 60:
            grade, label = "C", "Fair"
        elif score >= 45:
            grade, label = "D", "Needs Work"
        else:
            grade, label = "F", "Critical"

        return score, grade, label

    def _build_recommendations(self) -> str:
        """Build prioritized recommendations from analysis results."""
        immediate: list[str] = []
        medium: list[str] = []
        long_term: list[str] = []

        cov = self.jsdoc_coverage
        if cov and cov.get("coverage_pct", 100) < 80:
            undocumented = cov.get("total", 0) - cov.get("with_doc", 0)
            immediate.append(
                f"**Improve JSDoc coverage** — {undocumented} declarations lack JSDoc; "
                "prioritize high fan-in functions and exported API surface first"
            )

        if self.orphaned_functions:
            names = ", ".join(f"`{f.name}`" for f in self.orphaned_functions[:5])
            suffix = (
                f" (and {len(self.orphaned_functions) - 5} more)"
                if len(self.orphaned_functions) > 5
                else ""
            )
            immediate.append(
                f"**Audit orphaned declarations** — {names}{suffix} have zero callers; "
                "remove dead code or add tests/usage"
            )

        if self.high_fanout_functions:
            top = self.high_fanout_functions[0]
            immediate.append(
                f"**Refactor high fan-out orchestrators** — `{top.name}` calls {top.fan_out} others; "
                "split into smaller, focused coordinators"
            )

        top_fanin = sorted(self.function_metrics.values(), key=lambda m: m.fan_in, reverse=True)[:3]
        if top_fanin and top_fanin[0].fan_in > 1:
            names = ", ".join(f"`{m.name}`" for m in top_fanin)
            medium.append(
                f"**Harden high fan-in functions** — {names} are widely depended upon; "
                "review contracts, add type guards, and document edge cases"
            )

        if self.module_metrics:
            tightly_coupled = [
                m
                for m in self.module_metrics.values()
                if len(m.incoming_deps) + len(m.outgoing_deps) > 5
            ]
            if tightly_coupled:
                medium.append(
                    "**Reduce module coupling** — introduce interface boundaries or barrel "
                    "exports to decouple tightly coupled modules"
                )

        if self.critical_paths:
            medium.append(
                "**Add integration tests for key call chains** — the identified chains are "
                "well-traveled paths that benefit most from regression coverage"
            )

        inh = self.inheritance_analysis
        if inh and inh.get("max_depth", 0) > 3:
            long_term.append(
                "**Flatten deep inheritance** — prefer composition (mixins, generics) "
                "over deep class hierarchies in TypeScript"
            )

        if self.public_apis:
            long_term.append(
                "**Stabilize the exported API** — document breaking-change policies "
                f"for exported symbols: {', '.join(f'`{a.name}`' for a in self.public_apis[:3])}"
            )

        long_term.append(
            "**Enforce module boundaries in CI** — add import-lint rules to prevent "
            "accidental cross-layer coupling as the codebase grows"
        )

        if not immediate and not medium:
            immediate.append(
                "**Maintain current quality** — no critical issues detected; keep JSDoc "
                "coverage and module cohesion healthy"
            )

        lines = []
        if immediate:
            lines.append("### Immediate Actions")
            for i, rec in enumerate(immediate, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")
        if medium:
            lines.append("### Medium-term Refactoring")
            for i, rec in enumerate(medium, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")
        if long_term:
            lines.append("### Long-term Architecture")
            for i, rec in enumerate(long_term, 1):
                lines.append(f"{i}. {rec}")
        return "\n".join(lines)

    def _get_report_metadata(self, elapsed_seconds: float = 0.0) -> str:
        """Build a Markdown metadata block for the top of the report."""
        now = datetime.datetime.now(datetime.UTC)
        generated = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        version = "unknown"
        try:
            from importlib.metadata import version as _pkg_version  # noqa: PLC0415

            version = f"tscode-kg {_pkg_version('tscode-kg')}"
        except Exception:  # noqa: BLE001
            version = "tscode-kg (dev)"

        commit = os.environ.get("GITHUB_SHA", "")
        if commit:
            commit = commit[:7]
        else:
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    commit = result.stdout.strip()
            except (OSError, FileNotFoundError):
                pass
        commit = commit or "unknown"

        branch = ""
        github_ref = os.environ.get("GITHUB_REF", "")
        if github_ref.startswith("refs/heads/"):
            branch = github_ref[len("refs/heads/") :]
        if not branch:
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    branch = result.stdout.strip()
            except (OSError, FileNotFoundError):
                pass
        branch = branch or "unknown"

        try:
            _sys = platform.system()
            _mac = platform.mac_ver()[0]
            _os = f"macOS {_mac}" if _mac else f"{_sys} {platform.release()}"
            plat = f"{_os} | {platform.machine()} | Python {platform.python_version()}"
        except Exception:  # noqa: BLE001
            plat = "unknown"

        stats = self.stats or {}
        total_nodes = stats.get("total_nodes", "?")
        total_edges = stats.get("total_edges", "?")
        meaningful = stats.get("meaningful_nodes")
        graph_line = f"{total_nodes} nodes · {total_edges} edges"
        if meaningful is not None:
            graph_line += f" ({meaningful} meaningful)"

        dirs_line = ", ".join(sorted(self.include_dirs)) if self.include_dirs else "all"
        exclude_line = ", ".join(sorted(self.exclude_dirs)) if self.exclude_dirs else "none"

        elapsed_str = ""
        if elapsed_seconds > 0:
            mins, secs = divmod(int(elapsed_seconds), 60)
            elapsed_str = f"{mins}m {secs}s" if mins else f"{secs}s"

        return (
            "> **Analysis Report Metadata**  \n"
            f"> - **Generated:** {generated}  \n"
            f"> - **Version:** {version}  \n"
            f"> - **Commit:** {commit} ({branch})  \n"
            f"> - **Platform:** {plat}  \n"
            f"> - **Graph:** {graph_line}  \n"
            f"> - **Included directories:** {dirs_line}  \n"
            f"> - **Excluded directories:** {exclude_line}  \n"
            + (f"> - **Elapsed time:** {elapsed_str}  \n" if elapsed_str else "")
            + "\n"
        )

    def _write_report(self, report_path: str, elapsed_seconds: float = 0.0) -> None:
        """Write full Markdown analysis report to *report_path*."""
        report_date = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        stats = self.stats
        repo_name = Path(self.kg.repo_root).name
        quality_score, quality_grade, quality_label = self._compute_quality_grade()
        grade_tag = f"[{quality_grade}]"

        metadata = self._get_report_metadata(elapsed_seconds=elapsed_seconds)

        report = (
            metadata
            + f"""# {repo_name} — TypeScript/JavaScript Analysis

**Generated:** {report_date}

---

## Executive Summary

Comprehensive architectural analysis of **{repo_name}** using TypeScriptKG's knowledge graph.
Covers complexity hotspots, module coupling, call chains, JSDoc coverage, and type hierarchy.

| Overall Quality | Grade | Score |
|----------------|-------|-------|
| {grade_tag} **{quality_label}** | **{quality_grade}** | {quality_score:.0f} / 100 |

---

## Baseline Metrics

| Metric | Value |
|--------|-------|
| **Total Nodes** | {stats.get("total_nodes", "N/A")} |
| **Total Edges** | {stats.get("total_edges", "N/A")} |
| **Modules** | {stats.get("node_counts", {}).get("module", "N/A")} |
| **Functions** | {stats.get("node_counts", {}).get("function", "N/A")} |
| **Classes** | {stats.get("node_counts", {}).get("class", "N/A")} |
| **Methods** | {stats.get("node_counts", {}).get("method", "N/A")} |
| **Interfaces** | {stats.get("node_counts", {}).get("interface", "N/A")} |
| **Type Aliases** | {stats.get("node_counts", {}).get("type_alias", "N/A")} |
| **Enums** | {stats.get("node_counts", {}).get("enum", "N/A")} |

### Edge Distribution

| Relationship | Count |
|---|---|
| CALLS | {stats.get("edge_counts", {}).get("CALLS", 0)} |
| CONTAINS | {stats.get("edge_counts", {}).get("CONTAINS", 0)} |
| IMPORTS | {stats.get("edge_counts", {}).get("IMPORTS", 0)} |
| INHERITS | {stats.get("edge_counts", {}).get("INHERITS", 0)} |
| IMPLEMENTS | {stats.get("edge_counts", {}).get("IMPLEMENTS", 0)} |
| EXTENDS | {stats.get("edge_counts", {}).get("EXTENDS", 0)} |

---

## Fan-In Ranking

Most-called functions and methods — potential bottlenecks or core APIs.

| # | Kind | Name | Module | Callers |
|---|---|---|---|---|
"""
        )

        for i, metrics in enumerate(
            sorted(self.function_metrics.values(), key=lambda m: m.fan_in, reverse=True)[:15], 1
        ):
            report += f"| {i} | {metrics.kind} | `{metrics.name}` | {metrics.module} | **{metrics.fan_in}** |\n"

        report += """
**Insight:** High fan-in functions are core APIs or bottlenecks — review for type safety,
clear JSDoc contracts, and stable interfaces.

---

## High Fan-Out Functions (Orchestrators)

Functions that call many others may indicate complex orchestration or poor separation of concerns.

"""
        if self.high_fanout_functions:
            report += "| # | Name | Module | Calls | Type |\n|---|---|---|---|---|\n"
            for i, func in enumerate(
                sorted(self.high_fanout_functions, key=lambda f: f.fan_out, reverse=True)[:10], 1
            ):
                func_type = "Orchestrator" if func.fan_out > 40 else "Coordinator"
                report += (
                    f"| {i} | `{func.name}` | {func.module} | **{func.fan_out}** | {func_type} |\n"
                )
            report += "\n"
        else:
            report += "No extreme high fan-out functions detected. Well-balanced architecture.\n\n"

        report += """---

## Module Architecture

Cohesion = incoming-callers / (incoming + outgoing + 1). Higher = more internally focused.

"""
        if self.module_metrics:
            report += "| Module | Functions | Classes | Incoming | Outgoing | Cohesion |\n"
            report += "|---|---|---|---|---|---|\n"
            for module, m in sorted(
                self.module_metrics.items(),
                key=lambda x: x[1].functions + x[1].classes + x[1].methods,
                reverse=True,
            )[:12]:
                report += (
                    f"| `{module}` | {m.functions} | {m.classes} | "
                    f"{len(m.incoming_deps)} | {len(m.outgoing_deps)} | "
                    f"{m.cohesion_score:.2f} |\n"
                )
            report += "\n"

        report += "---\n\n## Key Call Chains\n\n"
        if self.critical_paths:
            for i, chain in enumerate(self.critical_paths[:5], 1):
                chain_str = " → ".join(chain.chain)
                report += f"**Chain {i}** (depth: {chain.depth})\n\n```\n{chain_str}\n```\n\n"
        else:
            report += "No deep call chains detected.\n\n"

        report += "---\n\n## Public API Surface\n\nExported declarations (top-level `export` keyword).\n\n"
        if self.public_apis:
            report += "| Name | Kind | Module | Callers |\n|---|---|---|---|\n"
            for api in sorted(self.public_apis, key=lambda a: a.fan_in, reverse=True)[:12]:
                report += f"| `{api.name}` | {api.kind} | {api.module} | {api.fan_in} |\n"
            report += "\n"
        else:
            report += "No exported declarations identified.\n\n"

        # JSDoc Coverage
        cov = self.jsdoc_coverage
        if cov:
            overall_pct = cov["coverage_pct"]
            pct_bar = "[OK]" if overall_pct >= 80 else "[WARN]" if overall_pct >= 50 else "[LOW]"
            report += "---\n\n## JSDoc Coverage\n\n"
            report += (
                "JSDoc coverage determines semantic retrieval quality. Nodes without JSDoc "
                "embed only structured identifiers — keyword search is as effective as vector "
                "embeddings. The semantic model earns its value only when JSDoc is present.\n\n"
            )
            report += "| Kind | Documented | Total | Coverage |\n|---|---|---|---|\n"
            for kind in ("function", "method", "class", "interface", "module"):
                if kind in cov["by_kind"]:
                    k = cov["by_kind"][kind]
                    kind_pct = (k["with_doc"] / k["total"] * 100) if k["total"] else 0.0
                    kind_bar = "[OK]" if kind_pct >= 80 else "[WARN]" if kind_pct >= 50 else "[LOW]"
                    report += (
                        f"| `{kind}` | {k['with_doc']} | {k['total']} | "
                        f"{kind_bar} {kind_pct:.1f}% |\n"
                    )
            report += (
                f"| **total** | **{cov['with_doc']}** | **{cov['total']}** | "
                f"**{pct_bar} {overall_pct:.1f}%** |\n\n"
            )
            if overall_pct < 80:
                undocumented = cov["total"] - cov["with_doc"]
                report += (
                    f"> **Recommendation:** {undocumented} declarations lack JSDoc. "
                    "Prioritize exported functions and high fan-in methods first.\n\n"
                )
        else:
            report += "---\n\n## JSDoc Coverage\n\nCoverage data not available.\n\n"

        # Structural Importance Ranking
        report += "---\n\n## Structural Importance Ranking (SIR)\n\n"
        if self.centrality_modules:
            report += (
                "Weighted PageRank aggregated by module. "
                "Cross-module edges boosted 1.5×; private symbols penalized 0.85×.\n\n"
            )
            report += "| Rank | Score | Members | Module |\n|---|---|---|---|\n"
            for mod in self.centrality_modules[:12]:
                report += (
                    f"| {mod['rank']} | {mod['score']:.6f} | {mod['member_count']} "
                    f"| `{mod['module_path']}` |\n"
                )
            report += "\n"
        else:
            report += "Centrality data not available.\n\n"

        # CodeRank top nodes
        report += "---\n\n## CodeRank — Global Structural Importance\n\n"
        if self.coderank_top_nodes:
            report += (
                "Weighted PageRank over CALLS + IMPORTS + INHERITS edges (test paths excluded). "
                "Scores normalized to sum to 1.0.\n\n"
            )
            report += "| Rank | Score | Kind | Name | Module |\n|---|---|---|---|---|\n"
            for i, n in enumerate(self.coderank_top_nodes[:20], 1):
                report += (
                    f"| {i} | {n['score']:.6f} | {n['kind']} "
                    f"| `{n['qualname'] or n['name']}` | {n['module_path']} |\n"
                )
            report += "\n"
        else:
            report += "CodeRank data not available.\n\n"

        # Issues / Strengths
        issues_text = (
            "\n".join(f"- {issue}" for issue in self.issues)
            if self.issues
            else "- No major issues detected"
        )
        strengths_text = (
            "\n".join(f"- {s}" for s in self.strengths)
            if self.strengths
            else "- Continue monitoring code quality"
        )

        report += f"""---

## Code Quality Issues

{issues_text}

---

## Architectural Strengths

{strengths_text}

---

## Recommendations

{self._build_recommendations()}

---

## Class and Interface Hierarchy

"""
        inh = self.inheritance_analysis
        if inh and (inh.get("total_inherits_edges", 0) + inh.get("total_implements_edges", 0)) > 0:
            report += (
                f"**{inh.get('total_inherits_edges', 0)}** INHERITS · "
                f"**{inh.get('total_implements_edges', 0)}** IMPLEMENTS · "
                f"**{inh.get('total_extends_edges', 0)}** interface EXTENDS\n\n"
            )
            if inh.get("classes"):
                report += "### Class Hierarchy (INHERITS)\n\n"
                report += "| Class | Module | Depth | Parents | Children |\n|---|---|---|---|---|\n"
                for cls in inh["classes"][:20]:
                    report += (
                        f"| `{cls['name']}` | {cls['module']} "
                        f"| {cls['depth']} | {cls['parent_count']} | {cls['child_count']} |\n"
                    )
                report += "\n"
            if inh.get("implements"):
                report += "### Class Implements Interface\n\n"
                report += "| Class | Interface | Module |\n|---|---|---|\n"
                for impl in inh["implements"][:15]:
                    report += f"| `{impl['class']}` | `{impl['interface']}` | {impl['module']} |\n"
                report += "\n"
            if inh.get("multiple_inheritance"):
                report += (
                    f"### Multiple Inheritance ({len(inh['multiple_inheritance'])} classes)\n\n"
                )
                for mi in inh["multiple_inheritance"]:
                    bases = ", ".join(f"`{b}`" for b in mi["bases"])
                    report += f"- `{mi['class']}` ({mi['module']}) extends {bases}\n"
                report += "\n"
        else:
            report += "No class hierarchy detected.\n"

        # Snapshot history
        report += "\n---\n\n## Snapshot History\n\n"
        if self.snapshot_history:
            report += "| # | Timestamp | Branch | Nodes | Edges |\n|---|---|---|---|---|\n"
            for i, snap in enumerate(self.snapshot_history, 1):
                ts = snap.get("timestamp", "")[:19].replace("T", " ")
                branch = snap.get("branch", "?")
                m = snap.get("metrics", {})
                report += f"| {i} | {ts} | {branch} | {m.get('total_nodes', '?')} | {m.get('total_edges', '?')} |\n"
        else:
            report += "No snapshots. Run `tscodekg snapshot save <version>` to capture one.\n"

        # Orphaned code appendix
        report += (
            "\n---\n\n## Appendix: Orphaned Declarations\n\nDeclarations with zero callers:\n\n"
        )
        if self.orphaned_functions:
            report += "| Name | Kind | Module | Lines |\n|---|---|---|---|\n"
            for func in sorted(self.orphaned_functions, key=lambda f: f.lines, reverse=True)[:15]:
                report += f"| `{func.name}` | {func.kind} | {func.module} | {func.lines} |\n"
        else:
            report += "No orphaned declarations detected.\n"

        elapsed_str = (
            f"{elapsed_seconds:.1f}s" if elapsed_seconds < 60 else f"{elapsed_seconds / 60:.1f}m"
        )
        report += (
            f"\n\n---\n\n*Report generated by TypeScriptKG analysis — completed in {elapsed_str}*\n"
        )

        Path(report_path).write_text(report, encoding="utf-8")
        self.console.print(f"[green]✓[/green] Report written to {report_path}")

    def _compile_results(self) -> dict:
        """Compile all phase results into a serialisable dictionary."""
        sorted_fn = sorted(self.function_metrics.items(), key=lambda kv: kv[1].fan_in, reverse=True)
        active_modules = {
            k: v
            for k, v in self.module_metrics.items()
            if v.total_fan_in > 0 or len(v.outgoing_deps) > 0
        }
        return {
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "statistics": self.stats,
            "jsdoc_coverage": self.jsdoc_coverage,
            "function_metrics": {k: asdict(v) for k, v in sorted_fn},
            "module_metrics": {k: asdict(v) for k, v in active_modules.items()},
            "orphaned_functions": [asdict(f) for f in self.orphaned_functions],
            "high_fanout_functions": [asdict(f) for f in self.high_fanout_functions],
            "critical_paths": [asdict(c) for c in self.critical_paths],
            "public_apis": [asdict(a) for a in self.public_apis],
            "issues": self.issues,
            "strengths": self.strengths,
            "inheritance": self.inheritance_analysis,
            "snapshot_history": self.snapshot_history,
            "centrality": [
                {
                    "rank": r.rank,
                    "node_id": r.node_id,
                    "kind": r.kind,
                    "name": r.name,
                    "module_path": r.module_path,
                    "score": r.score,
                }
                for r in self.centrality_records
            ],
            "centrality_modules": self.centrality_modules,
            "coderank_top_nodes": self.coderank_top_nodes,
        }

    def to_markdown(self) -> str:
        """Render analysis as a compact Markdown context document for LLM ingestion.

        Similar in spirit to ``SnippetPack.to_markdown()`` — structured,
        header-navigable output optimized for inclusion in AI prompts.

        :return: Markdown string covering all analysis phases.
        """
        out: list[str] = []
        stats = self.stats

        out.append("# TypeScriptKG Repository Analysis\n")
        out.append(f"**Generated:** {datetime.datetime.now(datetime.UTC).isoformat()}  \n")
        out.append("\n---\n")

        out.append("## Baseline Metrics\n")
        out.append("| Metric | Value |")
        out.append("|---|---|")
        out.append(f"| Total Nodes | {stats.get('total_nodes', 'N/A')} |")
        out.append(f"| Total Edges | {stats.get('total_edges', 'N/A')} |")
        out.append(f"| Modules | {stats.get('node_counts', {}).get('module', 'N/A')} |")
        out.append(f"| Functions | {stats.get('node_counts', {}).get('function', 'N/A')} |")
        out.append(f"| Classes | {stats.get('node_counts', {}).get('class', 'N/A')} |")
        out.append(f"| Methods | {stats.get('node_counts', {}).get('method', 'N/A')} |")
        out.append(f"| Interfaces | {stats.get('node_counts', {}).get('interface', 'N/A')} |")
        out.append("")

        out.append("### Edge Distribution")
        out.append("| Relationship | Count |")
        out.append("|---|---|")
        for rel in ("CALLS", "CONTAINS", "IMPORTS", "INHERITS", "IMPLEMENTS", "EXTENDS"):
            out.append(f"| {rel} | {stats.get('edge_counts', {}).get(rel, 0)} |")
        out.append("")

        out.append("## Fan-In Ranking\n")
        if self.function_metrics:
            out.append("| # | Kind | Name | Module | Callers |")
            out.append("|---|---|---|---|---|")
            for i, metrics in enumerate(
                sorted(self.function_metrics.values(), key=lambda m: m.fan_in, reverse=True)[:15], 1
            ):
                out.append(
                    f"| {i} | {metrics.kind} | `{metrics.name}` | {metrics.module} | {metrics.fan_in} |"
                )
        else:
            out.append("No high fan-in functions identified.\n")
        out.append("")

        out.append("## High Fan-Out Functions\n")
        if self.high_fanout_functions:
            out.append("| # | Name | Module | Calls |")
            out.append("|---|---|---|---|")
            for i, func in enumerate(
                sorted(self.high_fanout_functions, key=lambda f: f.fan_out, reverse=True)[:10], 1
            ):
                out.append(f"| {i} | `{func.name}` | {func.module} | {func.fan_out} |")
        else:
            out.append("No extreme high fan-out functions detected.\n")
        out.append("")

        out.append("## Module Architecture\n")
        if self.module_metrics:
            cap = min(10, len(self.module_metrics))
            out.append("| Module | Functions | Classes | Incoming | Outgoing | Cohesion |")
            out.append("|---|---|---|---|---|---|")
            for module, m in sorted(
                self.module_metrics.items(),
                key=lambda x: x[1].functions + x[1].classes + x[1].methods,
                reverse=True,
            )[:cap]:
                out.append(
                    f"| `{module}` | {m.functions} | {m.classes} | "
                    f"{len(m.incoming_deps)} | {len(m.outgoing_deps)} | "
                    f"{m.cohesion_score:.2f} |"
                )
        else:
            out.append("No module metrics available.\n")
        out.append("")

        out.append("## Key Call Chains\n")
        if self.critical_paths:
            for i, chain in enumerate(self.critical_paths[:5], 1):
                out.append(f"**Chain {i}** (depth: {chain.depth})\n")
                out.append(f"```\n{' → '.join(chain.chain)}\n```\n")
        else:
            out.append("No deep call chains detected.\n")
        out.append("")

        out.append("## Public API Surface\n")
        if self.public_apis:
            out.append("| Name | Kind | Module | Callers |")
            out.append("|---|---|---|---|")
            for api in sorted(self.public_apis, key=lambda a: a.fan_in, reverse=True)[:12]:
                out.append(f"| `{api.name}` | {api.kind} | {api.module} | {api.fan_in} |")
        else:
            out.append("No exported declarations identified.\n")
        out.append("")

        out.append("## JSDoc Coverage\n")
        cov = self.jsdoc_coverage
        if cov:
            out.append("| Kind | Documented | Total | Coverage |")
            out.append("|---|---|---|---|")
            for kind in ("function", "method", "class", "interface", "module"):
                if kind in cov["by_kind"]:
                    k = cov["by_kind"][kind]
                    kind_pct = (k["with_doc"] / k["total"] * 100) if k["total"] else 0.0
                    out.append(f"| `{kind}` | {k['with_doc']} | {k['total']} | {kind_pct:.1f}% |")
            overall_pct = cov["coverage_pct"]
            out.append(
                f"| **total** | **{cov['with_doc']}** | **{cov['total']}** | **{overall_pct:.1f}%** |"
            )
        else:
            out.append("Coverage data not available.\n")
        out.append("")

        out.append("## Class and Interface Hierarchy\n")
        inh = self.inheritance_analysis
        if inh and inh.get("total_inherits_edges", 0) > 0:
            out.append(
                f"{inh['total_inherits_edges']} INHERITS · "
                f"{inh.get('total_implements_edges', 0)} IMPLEMENTS · "
                f"{inh.get('total_extends_edges', 0)} iface-EXTENDS  "
                f"Max depth: {inh['max_depth']}\n"
            )
            out.append("| Class | Module | Depth | Parents | Children |")
            out.append("|---|---|---|---|---|")
            for cls in inh["classes"][:15]:
                out.append(
                    f"| `{cls['name']}` | {cls['module']} "
                    f"| {cls['depth']} | {cls['parent_count']} | {cls['child_count']} |"
                )
        else:
            out.append("No class hierarchy.\n")
        out.append("")

        quality_score, quality_grade, quality_label = self._compute_quality_grade()
        out.append("## Code Quality\n")
        out.append(f"**Grade: {quality_grade} ({quality_label}) — {quality_score:.0f}/100**\n")

        out.append("### Issues")
        for issue in self.issues:
            out.append(f"- {issue}")
        out.append("\n### Strengths")
        for s in self.strengths:
            out.append(f"- {s}")
        out.append("")

        return "\n".join(out)
