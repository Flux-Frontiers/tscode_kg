#!/usr/bin/env python3
"""
mcp_server.py — TypeScriptKG MCP Server

Exposes the TypeScriptKG hybrid query and snippet-pack pipeline as
Model Context Protocol (MCP) tools, allowing any MCP-compatible agent
(Claude Desktop, Cursor, Continue, etc.) to query a TypeScript/JavaScript
codebase knowledge graph directly.

Tools
-----
query_codebase(q, k, hop, rels, max_nodes, min_score, max_per_module, rerank_mode)
    Hybrid semantic + structural query. Returns ranked nodes and edges.

pack_snippets(q, k, hop, rels, context, max_lines, max_nodes, min_score, rerank_mode)
    Hybrid query + source-grounded snippet extraction.

callers(node_id, rel, paths)
    Reverse lookup: find all callers of a node, resolving sym: stubs.

get_node(node_id, include_edges)
    Fetch a single node by its stable ID.

graph_stats()
    Return node and edge counts by kind/relation as Markdown.

list_nodes(module_path, kind)
    List nodes filtered by module path prefix and/or kind.

find_node(name, kind)
    Find nodes by plain name or qualname substring.

centrality(top, kinds, group_by)
    SIR PageRank — rank nodes or modules by structural importance.

bridge_centrality(top, include_imports)
    Module connectivity — unique module interactions per module.

framework_nodes(top)
    Framework-like hub modules via SIR + module connectivity.

find_definition_at(file, line)
    Reverse-resolve a (file, line) location to a node and explain it.

analyze_repo()
    Run structural analysis and return a Markdown report.

explain(node_id, limit)
    Natural-language explanation of a node: callers, callees, role.

rank_nodes(top, rels, persist_metric, exclude_tests)
    Global weighted CodeRank (PageRank) over the repository graph.

query_ranked(q, k, mode, top, rels, radius, exclude_tests)
    CodeRank-enhanced hybrid or personalized-PageRank query ranking.

explain_rank(node_id, q)
    Explain the CodeRank score components for a specific node.

snapshot_list(limit, branch)
    List saved temporal metric snapshots, most recent first.

snapshot_show(key)
    Show full details of one snapshot ("latest" for the most recent).

snapshot_diff(key_a, key_b)
    Compare two metric snapshots side-by-side.

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kg_utils.semantic import DEFAULT_MODEL
from kg_utils.store import DEFAULT_RELS
from mcp.server.fastmcp import FastMCP

from tscode_kg.kg import TypeScriptKG
from tscode_kg.snapshots import SnapshotManager

# ---------------------------------------------------------------------------
# Global state — initialised in main()
# ---------------------------------------------------------------------------

_kg: TypeScriptKG | None = None
_snapshot_mgr: SnapshotManager | None = None


def _get_kg() -> TypeScriptKG:
    if _kg is None:
        raise RuntimeError(
            "TypeScriptKG not initialised. Run the server via 'tscodekg-mcp --repo /path/to/repo'"
        )
    return _kg


def _get_snapshot_mgr() -> SnapshotManager:
    if _snapshot_mgr is None:
        raise RuntimeError(
            "SnapshotManager not initialised. Run the server via 'tscodekg-mcp --repo /path/to/repo'"
        )
    return _snapshot_mgr


def _snapshot_freshness(snapshot_total_nodes: int) -> dict:
    """Compare a snapshot's node count against the currently loaded graph DB.

    :param snapshot_total_nodes: ``metrics.total_nodes`` from a snapshot object.
    :return: Freshness metadata payload.
    """
    current = _get_kg().stats()
    current_nodes = int(current.get("total_nodes", 0))
    delta = current_nodes - int(snapshot_total_nodes)

    is_fresh = delta == 0
    status = "fresh" if delta == 0 else ("behind" if delta > 0 else "ahead")
    note = None

    if 0 < delta < 50:
        is_fresh = True
        status = "near_fresh"
        note = "Within tolerance (sym: stubs often accumulate between rebuilds)"

    out = {
        "snapshot_total_nodes": int(snapshot_total_nodes),
        "current_total_nodes": current_nodes,
        "delta_nodes": delta,
        "is_fresh": is_fresh,
        "status": status,
    }
    if note:
        out["note"] = note
    return out


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "tscodekg",
    instructions=(
        "TypeScriptKG is a hybrid semantic + structural knowledge graph for TypeScript and "
        "JavaScript codebases. It indexes every module, class, interface, type alias, enum, "
        "function, and method as a node, with typed edges "
        "(CALLS, IMPORTS, CONTAINS, INHERITS, IMPLEMENTS, EXTENDS) connecting them.\n\n"
        "## Tools\n\n"
        "**graph_stats()** — Start here. Returns node/edge counts by kind and relation "
        "plus JSDoc coverage. Use before issuing query_codebase() or pack_snippets().\n\n"
        "**query_codebase(q, k, hop, rels, max_nodes, min_score, max_per_module, rerank_mode)** — "
        "Hybrid semantic + structural search. Seeds on vector similarity then expands through "
        "the graph. Returns ranked nodes and edges as JSON.\n\n"
        "**pack_snippets(q, k, hop, rels, context, max_lines, max_nodes, min_score, rerank_mode)** — "
        "Same hybrid search, but returns actual source code as a Markdown context pack "
        "with ranked, deduplicated snippets and line numbers.\n\n"
        "**callers(node_id, rel, paths)** — Precise reverse lookup: every node that calls "
        "(or inherits from, imports, …) the given node, resolving cross-module sym: stubs. "
        "Filter with paths='src/' to exclude test callers.\n\n"
        "**get_node(node_id, include_edges)** — Precise lookup of a single node by its stable "
        "ID (e.g. 'cls:src/auth/middleware.ts:AuthMiddleware').\n\n"
        "**list_nodes(module_path, kind)** — List nodes filtered by module path and/or kind.\n\n"
        "**find_node(name, kind)** — Find nodes by name substring when the stable ID is unknown.\n\n"
        "**centrality(top, kinds, group_by)** — Structural Importance Ranking (SIR): "
        "deterministic weighted PageRank over the graph. group_by='node' ranks individual "
        "nodes; group_by='module' aggregates per module. Use to find hotspots before "
        "refactoring or review.\n\n"
        "**bridge_centrality(top, include_imports)** — Module connectivity: how many unique "
        "modules each module calls or is called by. Identifies orchestrator/hub modules.\n\n"
        "**framework_nodes(top)** — Framework-like hub modules: 0.6 × SIR + 0.4 × "
        "connectivity (both normalized). Surfaces the repo-defining abstractions.\n\n"
        "**find_definition_at(file, line)** — Reverse-resolve a (file, line) location to the "
        "innermost enclosing node and return its explain() report.\n\n"
        "**analyze_repo()** — Structural analysis: node counts, edge counts, JSDoc coverage, "
        "node distribution by kind.\n\n"
        "**explain(node_id, limit)** — Natural-language Markdown explanation of a node: "
        "metadata, JSDoc, callers, callees, and its role in the codebase.\n\n"
        "**rank_nodes(top, rels, persist_metric, exclude_tests)** — Global weighted CodeRank "
        "(PageRank). Returns the most structurally important nodes as JSON.\n\n"
        "**query_ranked(q, k, mode, top, rels, radius, exclude_tests)** — Query ranking that "
        "combines semantic seeds with centrality and graph proximity ('hybrid') or "
        "personalized PageRank ('ppr'); results include 'why' explanations.\n\n"
        "**explain_rank(node_id, q)** — Break down a node's CodeRank score: global rank, "
        "inbound/outbound structural edges, and optional query-conditioned scores.\n\n"
        "**snapshot_list(limit, branch)** — List saved temporal metric snapshots (most recent "
        "first) with per-snapshot deltas and freshness vs. the live graph.\n\n"
        "**snapshot_show(key)** — Full details of one snapshot; pass 'latest' (default) for "
        "the most recent.\n\n"
        "**snapshot_diff(key_a, key_b)** — Side-by-side comparison of two snapshots with "
        "computed deltas (b − a).\n\n"
        "## Recommended Workflows\n\n"
        "- **Explore unfamiliar TS/JS repo**: graph_stats → query_codebase → pack_snippets\n"
        "- **Find a specific class/function**: find_node(name) → get_node(include_edges=True)\n"
        "- **Understand an interface**: get_node → pack_snippets\n"
        "- **Trace usage of a symbol**: find_node(name) → callers(node_id)\n"
        "- **Identify structural hotspots**: centrality(top=20) or centrality(group_by='module')\n"
        "- **Architecture review**: analyze_repo\n"
        "- **Track codebase evolution**: snapshot_list → snapshot_diff(key_a, key_b)\n"
        "- **Answer 'how does X work?'**: pack_snippets with a descriptive query\n"
    ),
)


@mcp.tool()
def query_codebase(
    q: str,
    k: int = 8,
    hop: int = 1,
    rels: str = "CONTAINS,CALLS,IMPORTS,INHERITS,IMPLEMENTS,EXTENDS",
    max_nodes: int = 25,
    min_score: float = 0.0,
    max_per_module: int = 3,
    rerank_mode: str = "hybrid",
    rerank_semantic_weight: float = 0.7,
    rerank_lexical_weight: float = 0.3,
    format: str = "json",
) -> str:
    """
    Hybrid semantic + structural query over the TypeScript/JavaScript codebase graph.

    :param q: Natural-language query, e.g. "authentication middleware".
    :param k: Number of semantic seed nodes (default 8).
    :param hop: Graph expansion hops (default 1).
    :param rels: Comma-separated edge types to follow.
    :param max_nodes: Maximum nodes to return (default 25).
    :param min_score: Minimum semantic score for seed inclusion in [0, 1].
    :param max_per_module: Maximum nodes per module (default 3; 0 disables).
    :param rerank_mode: 'hybrid' (default), 'semantic', or 'legacy'.
    :param rerank_semantic_weight: Semantic weight for hybrid mode (default 0.7).
    :param rerank_lexical_weight: Lexical weight for hybrid mode (default 0.3).
    :param format: 'json' (default) or 'markdown'.
    :return: JSON string or Markdown table.
    """
    rel_tuple = tuple(r.strip() for r in rels.split(",") if r.strip())
    result = _get_kg().query(
        q,
        k=k,
        hop=hop,
        rels=rel_tuple or DEFAULT_RELS,
        max_nodes=max_nodes,
        min_score=min_score,
        max_per_module=max_per_module if max_per_module > 0 else None,
        rerank_mode=rerank_mode,
        rerank_semantic_weight=rerank_semantic_weight,
        rerank_lexical_weight=rerank_lexical_weight,
    )
    data = json.loads(result.to_json())

    if format == "markdown":
        out: list[str] = [
            f"## Query Results: `{q}`\n",
            f"**Seeds:** {data['seeds']}  |  "
            f"**Expanded:** {data['expanded_nodes']}  |  "
            f"**Returned:** {data['returned_nodes']}\n",
            "| Rank | Score | Kind | Name | Module |",
            "|-----:|------:|------|------|--------|",
        ]
        for rank_idx, node in enumerate(data["nodes"], start=1):
            score = node.get("relevance", {}).get("score", 0.0)
            kind = node.get("kind", "?")
            name = node.get("qualname") or node.get("name", "?")
            module = node.get("module_path", "")
            out.append(f"| {rank_idx} | {score:.3f} | {kind} | `{name}` | `{module}` |")
        return "\n".join(out)

    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
def pack_snippets(
    q: str,
    k: int = 8,
    hop: int = 1,
    rels: str = "CONTAINS,CALLS,IMPORTS,INHERITS,IMPLEMENTS,EXTENDS",
    context: int = 5,
    max_lines: int = 60,
    max_nodes: int = 15,
    min_score: float = 0.0,
    max_per_module: int = 3,
    rerank_mode: str = "hybrid",
    rerank_semantic_weight: float = 0.7,
    rerank_lexical_weight: float = 0.3,
) -> str:
    """
    Hybrid query + source-grounded TypeScript/JS snippet extraction.

    Returns a Markdown context pack with ranked, deduplicated code snippets
    and line numbers — ready for direct LLM ingestion.

    :param q: Natural-language query, e.g. "error handling middleware".
    :param k: Number of semantic seed nodes (default 8).
    :param hop: Graph expansion hops (default 1).
    :param rels: Comma-separated edge types to follow.
    :param context: Extra context lines around each definition (default 5).
    :param max_lines: Maximum lines per snippet block (default 60).
    :param max_nodes: Maximum nodes to include in the pack (default 15).
    :param min_score: Minimum semantic score for seed inclusion in [0, 1].
    :param max_per_module: Maximum nodes per module (default 3; 0 disables).
    :param rerank_mode: 'hybrid' (default), 'semantic', or 'legacy'.
    :param rerank_semantic_weight: Semantic weight for hybrid mode (default 0.7).
    :param rerank_lexical_weight: Lexical weight for hybrid mode (default 0.3).
    :return: Markdown string with source-grounded code snippets.
    """
    rel_tuple = tuple(r.strip() for r in rels.split(",") if r.strip())
    pack = _get_kg().pack(
        q,
        k=k,
        hop=hop,
        rels=rel_tuple or DEFAULT_RELS,
        context=context,
        max_lines=max_lines,
        max_nodes=max_nodes,
        min_score=min_score,
        max_per_module=max_per_module if max_per_module > 0 else None,
        rerank_mode=rerank_mode,
        rerank_semantic_weight=rerank_semantic_weight,
        rerank_lexical_weight=rerank_lexical_weight,
    )
    return pack.to_markdown()


@mcp.tool()
def callers(node_id: str, rel: str = "CALLS", paths: str = "") -> str:
    """
    Return all nodes that call a given node, resolving through ``sym:`` stubs.

    Unlike ``query_codebase`` (which seeds on semantics and expands outward),
    this tool performs a precise reverse lookup: it finds every caller of the
    specified node, including cross-module callers that reference it via an
    import alias recorded as a ``sym:`` stub.

    The ``rel`` parameter accepts any edge relation, not just ``CALLS``::

        callers(node_id, rel="INHERITS")    # find all subclasses
        callers(node_id, rel="IMPLEMENTS")  # find all implementations
        callers(node_id, rel="IMPORTS")     # find all importers

    Typical workflow::

        # 1. Resolve the exact node ID
        get_node("fn:src/utils/helpers.ts:formatDate")

        # 2. Find all callers (production code only)
        callers("fn:src/utils/helpers.ts:formatDate", paths="src/")

    :param node_id: Target node identifier, e.g.
                    ``cls:src/auth/middleware.ts:AuthMiddleware``.
    :param rel: Relation type to invert (default ``"CALLS"``).
    :param paths: Comma-separated module path prefixes to include, e.g.
                  ``"src/"`` to exclude test callers.
                  Empty string (default) returns all callers.
    :return: JSON with ``node_id``, ``rel``, ``caller_count``, and
             ``callers`` list of node dicts.
    """
    caller_list = _get_kg().callers(node_id, rel=rel)
    if paths:
        path_prefixes = [p.strip() for p in paths.split(",") if p.strip()]
        caller_list = [
            c
            for c in caller_list
            if any((c.get("module_path") or "").startswith(pfx) for pfx in path_prefixes)
        ]
    return json.dumps(
        {
            "node_id": node_id,
            "rel": rel,
            "caller_count": len(caller_list),
            "callers": caller_list,
        },
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
def get_node(node_id: str, include_edges: bool = False) -> str:
    """
    Fetch a single TypeScript/JS node by its stable ID and render as Markdown.

    Node IDs follow the pattern ``<kind>:<module_path>:<qualname>``, e.g.
    ``cls:src/auth/middleware.ts:AuthMiddleware`` or
    ``fn:src/utils/helpers.ts:formatDate``.

    :param node_id: Stable node identifier.
    :param include_edges: If True, append outgoing edges and incoming callers.
    :return: Markdown-formatted node summary.
    """
    kg = _get_kg()
    node = kg.node(node_id)
    if node is None:
        return f"## Node Not Found\n\nNode ID `{node_id}` does not exist in the knowledge graph."

    kind = node.get("kind", "unknown")
    name = node.get("qualname") or node.get("name", "unknown")
    out: list[str] = [f"## `{name}` ({kind})\n"]

    module = node.get("module_path", "")
    lineno = node.get("lineno")
    end_lineno = node.get("end_lineno")
    if module:
        out.append(f"- **Module:** `{module}`")
    if lineno is not None:
        loc = f"line {lineno}"
        if end_lineno:
            loc += f"–{end_lineno}"
        out.append(f"- **Location:** {loc}")
    out.append(f"- **ID:** `{node_id}`")
    out.append("")

    docstring = node.get("docstring", "").strip()
    if docstring:
        out.append("### JSDoc\n")
        out.append(docstring)
        out.append("")

    if not include_edges:
        return "\n".join(out)

    store = getattr(kg, "_store", None)
    if store is not None:
        for rel in ("CALLS", "CONTAINS", "IMPORTS", "INHERITS", "IMPLEMENTS", "EXTENDS"):
            edges = store.edges_from(node_id, rel=rel)
            visible = [e for e in edges if not e["dst"].startswith("sym:")] if edges else []
            if visible:
                out.append(f"### Outgoing {rel}\n")
                for e in visible:
                    out.append(f"- `{e['dst']}`")
                out.append("")

    try:
        caller_nodes = kg.callers(node_id, rel="CALLS")
        if caller_nodes:
            out.append("### Incoming Calls\n")
            for c in caller_nodes:
                cname = c.get("qualname") or c.get("name", "")
                cmod = c.get("module_path", "")
                cline = c.get("lineno")
                cid = c.get("id", "")
                loc_str = f" (line {cline})" if cline else ""
                out.append(f"- `{cid}` — `{cname}` in `{cmod}`{loc_str}")
            out.append("")
    except (AttributeError, ValueError, RuntimeError):
        pass

    return "\n".join(out)


@mcp.tool()
def graph_stats() -> str:
    """
    Return node and edge counts by kind and relation as Markdown.

    Call this first when engaging with a new TypeScript/JavaScript repo.
    Reports JSDoc coverage (fraction of functions/methods with JSDoc comments).

    :return: Markdown summary with total counts, nodes-by-kind, and edges-by-relation tables.
    """
    stats = _get_kg().stats()
    out: list[str] = ["## TypeScriptKG Graph Statistics\n"]
    out.append(f"- **Database:** `{stats.get('db_path', '')}`")
    out.append(f"- **Total nodes:** {stats.get('total_nodes', 0):,}")
    out.append(
        f"- **Meaningful nodes:** {stats.get('meaningful_nodes', 0):,} *(excludes sym: stubs)*"
    )
    out.append(f"- **Total edges:** {stats.get('total_edges', 0):,}")
    cov = stats.get("docstring_coverage")
    if cov is not None:
        out.append(f"- **JSDoc coverage:** {cov:.1%} *(functions + methods)*")
    out.append("")

    node_counts: dict = stats.get("node_counts", {})
    if node_counts:
        out.append("### Nodes by Kind\n")
        out.append("| Kind | Count |")
        out.append("|------|------:|")
        for kind, count in sorted(node_counts.items(), key=lambda x: -x[1]):
            out.append(f"| {kind} | {count:,} |")
        out.append("")

    edge_counts: dict = stats.get("edge_counts", {})
    if edge_counts:
        out.append("### Edges by Relation\n")
        out.append("| Relation | Count |")
        out.append("|----------|------:|")
        for rel, count in sorted(edge_counts.items(), key=lambda x: -x[1]):
            out.append(f"| {rel} | {count:,} |")
        out.append("")

    out.append(
        "> `sym:` nodes are import stub placeholders for external packages — "
        "they are not local code entities."
    )
    return "\n".join(out)


@mcp.tool()
def list_nodes(
    module_path: str = "",
    kind: str = "",
) -> str:
    """
    List nodes filtered by module path prefix and/or kind.

    :param module_path: Module path prefix filter (e.g. "src/auth/middleware.ts").
    :param kind: Node kind filter: module | class | interface | type_alias | enum |
                 namespace | function | method.
    :return: JSON array of matching node dicts.
    """
    kg = _get_kg()
    store = getattr(kg, "_store", None)
    if not store:
        return json.dumps({"error": "No database store available."}, indent=2)

    q = "SELECT id, name, qualname, kind, module_path, lineno, docstring FROM nodes WHERE 1=1"
    q += " AND id NOT LIKE 'sym:%'"
    params = []

    if module_path:
        q += " AND module_path LIKE ?"
        params.append(f"{module_path}%")
    if kind:
        q += " AND kind = ?"
        params.append(kind)

    q += " ORDER BY module_path, lineno"

    try:
        rows = store.con.execute(q, params).fetchall()
        result = []
        for r in rows:
            doc = r[6]
            if doc and len(doc) > 120:
                doc = doc[:120] + "..."
            result.append(
                {
                    "id": r[0],
                    "name": r[1],
                    "qualname": r[2],
                    "kind": r[3],
                    "module_path": r[4],
                    "lineno": r[5],
                    "docstring": doc,
                }
            )
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:  # pylint: disable=broad-except
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def find_node(name: str, kind: str = "") -> str:
    """
    Find graph nodes by name without knowing their full stable ID.

    Case-insensitive match against name and qualname. Use when you know a
    function or class name from reading code and need its stable ID.

    :param name: Function, class, or interface name to search for.
    :param kind: Optional kind filter: module | class | interface | function | method | etc.
    :return: JSON array of matching node dicts.
    """
    kg = _get_kg()
    store = getattr(kg, "_store", None)
    if not store:
        return json.dumps({"error": "No database store available."}, indent=2)

    name_lower = name.lower()
    q = (
        "SELECT id, name, qualname, kind, module_path, lineno, docstring "
        "FROM nodes WHERE (LOWER(name) = ? OR LOWER(qualname) LIKE ?)"
        " AND id NOT LIKE 'sym:%'"
    )
    params: list = [name_lower, f"%{name_lower}%"]
    if kind:
        q += " AND kind = ?"
        params.append(kind)
    q += " ORDER BY module_path, lineno"

    try:
        rows = store.con.execute(q, params).fetchall()
        result = []
        for r in rows:
            doc = r[6]
            if doc and len(doc) > 120:
                doc = doc[:120] + "..."
            result.append(
                {
                    "id": r[0],
                    "name": r[1],
                    "qualname": r[2],
                    "kind": r[3],
                    "module_path": r[4],
                    "lineno": r[5],
                    "docstring": doc,
                }
            )
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:  # pylint: disable=broad-except
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def centrality(
    top: int = 20,
    kinds: str = "",
    group_by: str = "node",
) -> str:
    """
    Compute Structural Importance Ranking (SIR) for the indexed codebase.

    Runs a deterministic weighted PageRank over the sym-stub-resolved call
    graph.  Edge weights are tuned per relation type
    (CALLS > INHERITS/IMPLEMENTS > IMPORTS > CONTAINS) and amplified for
    cross-module links; private symbols receive a post-convergence penalty.
    Scores are normalized to sum to 1.0.

    Use this to:

    - Identify the most structurally critical functions, classes, and interfaces
    - Understand which modules are most depended upon
    - Prioritize code review, refactoring, or test coverage efforts

    :param top: Maximum number of ranked entries to return (default 20).
    :param kinds: Comma-separated node kinds to include: ``module``, ``class``,
                  ``interface``, ``function``, ``method``.  Empty string returns
                  all kinds.  Ignored when ``group_by='module'`` (all kinds
                  contribute to module aggregation).
    :param group_by: ``node`` (default) returns individual node rankings with
                     score, inbound edge count, and cross-module inbound count;
                     ``module`` aggregates node scores per module.
    :return: Markdown-formatted ranking table.
    """
    try:
        from tscode_kg.centrality import (  # noqa: PLC0415
            StructuralImportanceRanker,
            aggregate_module_scores,
        )

        db_path = _get_kg().db_path
        ranker = StructuralImportanceRanker(db_path)
        all_records = ranker.compute()
    except Exception as e:  # noqa: BLE001
        return f"## Centrality Error\n\nFailed to compute SIR scores: `{e}`"

    out: list[str] = ["## Structural Importance Ranking (SIR)\n"]

    if group_by == "module":
        payload = aggregate_module_scores(all_records)[:top]
        out.append(f"**Group by:** module  |  **Top:** {top}\n")
        out.append("| Rank | Score | Members | Module |")
        out.append("|-----:|------:|--------:|--------|")
        for row in payload:
            out.append(
                f"| {row['rank']} | {row['score']:.6f}"
                f" | {row['member_count']} | `{row['module_path']}` |"
            )
    else:
        kind_set: set[str] | None = None
        if kinds.strip():
            kind_set = {k.strip().lower() for k in kinds.split(",") if k.strip()}

        filtered = [r for r in all_records if kind_set is None or r.kind in kind_set][:top]
        label = kinds if kind_set else "all kinds"
        out.append(f"**Group by:** node  |  **Top:** {top}  |  **Filter:** {label}\n")
        out.append("| Rank | Score | Kind | Name | Module | Inbound | XMod |")
        out.append("|-----:|------:|------|------|--------|--------:|-----:|")
        for r in filtered:
            module = f"`{r.module_path}`" if r.module_path else "—"
            out.append(
                f"| {r.rank} | {r.score:.6f} | {r.kind} | `{r.name}`"
                f" | {module} | {r.inbound_count} | {r.cross_module_inbound} |"
            )

    out.append("")
    out.append(
        "> SIR scores are normalized to sum 1.0 across all nodes.  "
        "Higher score = more structurally central.  "
        "XMod = cross-module inbound edges."
    )
    return "\n".join(out)


@mcp.tool()
def bridge_centrality(
    top: int = 20,
    include_imports: bool = True,
) -> str:
    """
    Compute module connectivity: how many unique modules each module interacts with.

    For well-modularized codebases, identifies orchestrator and hub modules that
    touch many other modules. Replaces betweenness centrality (which is meaningless
    when inter-module edges are zero).

    **Connectivity score** = (unique modules called + unique modules calling this) / 30 + frequency / 50
    Higher score = more complex coupling with other modules.

    Scores are persisted to the ``centrality_scores`` table under the
    ``module_connectivity`` metric for use by ``framework_nodes()``.

    :param top: Number of top connectivity modules to return (default 20).
    :param include_imports: Whether to include IMPORTS in connectivity (default True).
    :return: Markdown-formatted ranking table of modules by connectivity.
    """
    try:
        from tscode_kg.bridge import compute_bridge_centrality  # noqa: PLC0415

        db_path = str(_get_kg().db_path)
        modules = compute_bridge_centrality(
            kind="module",
            include_imports=include_imports,
            top=top,
            db_path=db_path,
        )
    except Exception as e:  # noqa: BLE001
        return f"## Module Connectivity Error\n\nFailed to compute connectivity: `{e}`"

    out: list[str] = ["## Module Connectivity (Interaction Complexity)\n"]
    out.append(f"**Top:** {top}  |  **Include imports:** {include_imports}\n")
    out.append("| Rank | Connectivity | Module |")
    out.append("|-----:|-------------:|--------|")
    for rank_idx, (mod, score) in enumerate(modules, start=1):
        out.append(f"| {rank_idx} | {score:.6f} | `{mod}` |")
    out.append("")
    out.append(
        "> Connectivity = unique modules called + unique modules calling this module.  "
        "Higher score = orchestrator/hub module with complex interactions.  "
        "Scores are persisted as `module_connectivity` metric for use by `framework_nodes()`."
    )
    return "\n".join(out)


@mcp.tool()
def framework_nodes(top: int = 20) -> str:
    """
    Identify framework-like (hub) modules using SIR + module connectivity.

    A "framework node" is a module that is both:
    - Structurally important (high SIR/PageRank — central to the graph)
    - Highly connected (calls/imports many modules — orchestrator/hub role)

    Framework score = 0.6 × normalized SIR + 0.4 × normalized connectivity,
    both auto-computed on first call. High-scoring modules are critical hubs:
    architecturally central AND complex in their interactions.

    :param top: Number of top framework-like modules to return (default 20).
    :return: Markdown-formatted ranking table of framework nodes.
    """
    try:
        from tscode_kg.bridge import compute_bridge_centrality  # noqa: PLC0415
        from tscode_kg.centrality import StructuralImportanceRanker  # noqa: PLC0415
        from tscode_kg.framework_detector import detect_framework_nodes  # noqa: PLC0415

        kg = _get_kg()
        db_path = str(kg.db_path)

        # Compute and persist SIR scores (structural importance)
        try:
            ranker = StructuralImportanceRanker(db_path)
            records = ranker.compute()
            ranker.write_scores(records, metric="sir_pagerank")
        except Exception as e:  # noqa: BLE001
            return f"## Framework Nodes Error\n\nFailed to compute SIR scores: `{e}`"

        # Compute and persist module connectivity scores (interaction complexity)
        try:
            compute_bridge_centrality(kind="module", include_imports=True, top=25, db_path=db_path)
        except Exception as e:  # noqa: BLE001
            return f"## Framework Nodes Error\n\nFailed to compute module connectivity: `{e}`"

        # Detect framework nodes by combining both metrics
        nodes = detect_framework_nodes(limit=top, db_path=db_path)
    except Exception as e:  # noqa: BLE001
        return f"## Framework Nodes Error\n\nFailed to detect framework nodes: `{e}`"

    out: list[str] = ["## Framework-like Modules (Critical Hubs)\n"]
    out.append(f"**Top:** {top}  |  **Score:** 0.6 × SIR + 0.4 × connectivity (both normalized)\n")
    out.append("| Rank | Score | Module |")
    out.append("|-----:|------:|--------|")
    for rank_idx, (_, score, label) in enumerate(nodes, start=1):
        out.append(f"| {rank_idx} | {score:.6f} | `{label}` |")
    out.append("")
    out.append(
        "> Framework nodes: both architecturally central (SIR) AND heavily connected "
        "(calls/imports many modules).  High-scoring modules are critical orchestrators/hubs."
    )
    return "\n".join(out)


@mcp.tool()
def find_definition_at(file: str, line: int) -> str:
    """
    Find the code node whose definition spans a given file location.

    Reverse-resolves a ``(file, line)`` pair to a graph node ID and returns the
    same Markdown report as ``explain()``.  Useful when reading a file in an IDE
    and wanting to understand the symbol at a specific line without constructing
    a node ID manually.

    Matches the innermost (most-specific) function, method, class, interface,
    type alias, or enum whose ``lineno ≤ line ≤ end_lineno``.  Falls back to
    the module node when no narrower match exists.

    :param file: Module path as stored in the graph, e.g. ``src/auth/middleware.ts``.
                 Leading ``./`` is stripped automatically.
    :param line: Line number (1-indexed) within the file.
    :return: Markdown explanation from ``explain()``, or an informative error
             message if no node spans that location.
    """
    kg = _get_kg()
    store = getattr(kg, "_store", None) or getattr(kg, "store", None)
    if store is None:
        return "## Error\n\nNo graph store available."

    norm_file = file.lstrip("./")

    # Innermost span: smallest (end_lineno - lineno) that still contains `line`.
    rows = store.con.execute(
        """
        SELECT id
        FROM nodes
        WHERE (module_path = :f OR module_path LIKE :like)
          AND kind IN ('function', 'method', 'class', 'interface', 'type_alias', 'enum')
          AND lineno IS NOT NULL
          AND lineno <= :ln
          AND (end_lineno IS NULL OR end_lineno >= :ln)
        ORDER BY (COALESCE(end_lineno, lineno) - lineno) ASC
        LIMIT 1
        """,
        {"f": norm_file, "like": f"%{norm_file}", "ln": line},
    ).fetchall()

    if not rows:
        # Fall back to the module node itself
        mod_rows = store.con.execute(
            "SELECT id FROM nodes WHERE kind = 'module' AND (module_path = ? OR module_path LIKE ?)",
            (norm_file, f"%{norm_file}"),
        ).fetchall()
        if not mod_rows:
            return (
                f"## No Definition Found\n\n"
                f"No function, method, class, interface, type alias, or enum spans "
                f"`{file}:{line}` in the graph.\n\n"
                "Check that the file path matches the module path stored in the graph "
                "(use `graph_stats()` or `list_nodes()` to browse available modules)."
            )
        node_id = mod_rows[0][0]
    else:
        node_id = rows[0][0]

    return explain(node_id)


@mcp.tool()
def analyze_repo() -> str:
    """
    Run a full structural analysis of the indexed TypeScript/JavaScript repository.

    Executes the 14-phase TypeScriptKG analysis pipeline — baseline metrics,
    CodeRank, fan-in/fan-out, module coupling, critical call chains, public API
    surface, JSDoc coverage, class/interface hierarchy, insights, snapshot
    history, and SIR centrality — and returns the results as Markdown.

    :return: Markdown-formatted analysis report.
    """
    from io import StringIO  # noqa: PLC0415

    from rich.console import Console  # noqa: PLC0415

    from tscode_kg.analysis import TSCodeKGAnalyzer  # noqa: PLC0415
    from tscode_kg.kg import _render_analysis  # noqa: PLC0415

    # Silence Rich output — stdout carries the MCP protocol on stdio transport.
    silent = Console(file=StringIO(), highlight=False)
    kg = _get_kg()
    try:
        analyzer = TSCodeKGAnalyzer(kg, console=silent, snapshot_mgr=_snapshot_mgr)
        analyzer.run_analysis()
        return analyzer.to_markdown()
    except Exception as exc:  # noqa: BLE001
        # Lightweight stats-only fallback — never re-runs the noisy analyzer.
        try:
            return _render_analysis(str(kg.repo_root), kg.store.stats())
        except Exception:  # noqa: BLE001
            return f"# TypeScriptKG Analysis\n\nAnalysis failed: {exc}\n"


@mcp.tool()
def explain(node_id: str, limit: int = 10) -> str:
    """
    Return a natural-language explanation of a code node.

    Given a node ID (e.g., ``fn:src/utils/helpers.ts:formatDate``),
    returns a markdown-formatted explanation that includes:

    - **What it is**: The node's kind, short description from its JSDoc
    - **Where it lives**: Module path and source location
    - **What calls it**: The callers (reverse call graph)
    - **What it calls**: The callees (functions/methods this node invokes)
    - **Documentation**: Full JSDoc if available

    This is ideal for understanding the role and context of a specific node
    without needing to read the full source code. Use ``pack_snippets()``
    to then retrieve the actual implementation.

    :param node_id: Stable node identifier, e.g.
                    ``fn:src/utils/helpers.ts:formatDate``.
    :param limit: Maximum callers and callees to list (default 10). Pass 0
                  to list all.
    :return: Markdown-formatted explanation ready for LLM consumption.
    """
    from tscode_kg.explain import render_explain  # noqa: PLC0415

    return render_explain(
        _get_kg(),
        node_id,
        limit=limit,
        snippets_hint="pack_snippets()",
    )


@mcp.tool()
def rank_nodes(
    top: int = 25,
    rels: str = "CALLS,IMPORTS,INHERITS,IMPLEMENTS,EXTENDS",
    persist_metric: str = "",
    exclude_tests: bool = True,
) -> str:
    """
    Compute global weighted CodeRank (PageRank) over the repository graph.

    Builds a directed weighted graph from the SQLite store and runs weighted
    PageRank to identify the most structurally important nodes.  Relation
    weights follow the CodeRank defaults: CALLS=1.0, IMPORTS=0.9,
    INHERITS/IMPLEMENTS/EXTENDS=0.75.  Test paths are excluded by default.

    Optionally persists the scores into the ``node_metrics`` table under the
    given metric name so they can be loaded at query time without recomputing.

    :param top: Number of top-ranked nodes to return (default 25).
    :param rels: Comma-separated relations to include in the graph
                 (default ``"CALLS,IMPORTS,INHERITS,IMPLEMENTS,EXTENDS"``).
    :param persist_metric: If non-empty, persist scores to ``node_metrics``
                           under this metric name (e.g. ``"coderank_global"``).
    :param exclude_tests: Exclude test-path nodes from the graph (default True).
    :return: JSON array of ranked node dicts with ``node_id``, ``score``,
             ``top_pct`` (e.g. ``"top 0.5%"``), ``kind``, ``qualname``,
             ``module_path``, and ``rank`` fields.
    """
    from tscode_kg.coderank import (  # noqa: PLC0415
        build_code_graph,
        compute_coderank,
        persist_metric_scores,
    )

    db_path = str(_get_kg().db_path)
    rel_list = [r.strip() for r in rels.split(",") if r.strip()]

    try:
        graph = build_code_graph(
            db_path,
            include_relations=rel_list,
            exclude_test_paths=exclude_tests,
        )
        scores = compute_coderank(graph)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)}, indent=2)

    if persist_metric:
        try:
            persist_metric_scores(db_path, persist_metric, scores)
        except Exception:  # noqa: BLE001
            pass  # non-fatal — still return results

    # Filter out sym: stubs (import placeholders) — only return real code entities
    all_real_nodes = [
        (nid, s)
        for nid, s in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        if not nid.startswith("sym:")
    ]
    total_real = len(all_real_nodes)
    results = []
    for rank_idx, (node_id, score) in enumerate(all_real_nodes[:top], start=1):
        attrs = graph.nodes.get(node_id, {})
        top_pct = round(rank_idx / total_real * 100, 1) if total_real > 0 else 0.0
        results.append(
            {
                "rank": rank_idx,
                "node_id": node_id,
                "score": round(score, 8),
                "top_pct": f"top {top_pct:.1f}%",
                "kind": attrs.get("kind"),
                "qualname": attrs.get("qualname"),
                "module_path": attrs.get("module_path"),
            }
        )

    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool()
def query_ranked(
    q: str,
    k: int = 8,
    mode: str = "hybrid",
    top: int = 25,
    rels: str = "CALLS,IMPORTS,INHERITS,IMPLEMENTS,EXTENDS",
    radius: int = 2,
    exclude_tests: bool = True,
) -> str:
    """
    Rank query results using CodeRank-enhanced hybrid or personalized PageRank.

    Combines semantic seed scores from the vector index with structural
    centrality and graph proximity to produce a final ranked list with
    explainability components.

    Two modes are available:

    - ``hybrid`` (default): 0.60 × semantic + 0.25 × centrality + 0.15 × proximity
    - ``ppr``: 0.70 × personalized PageRank + 0.30 × semantic

    :param q: Natural-language query string.
    :param k: Number of semantic seed nodes to retrieve (default 8).
    :param mode: Ranking mode — ``"hybrid"`` (default) or ``"ppr"``.
    :param top: Maximum ranked results to return (default 25).
    :param rels: Comma-separated relations to include in the local graph.
    :param radius: Graph expansion radius around seeds (default 2).
    :param exclude_tests: Exclude test-path nodes (default True).
    :return: JSON array of ranked result dicts with score components and
             ``why`` explanation strings.  ``sym:`` import stub nodes are
             always excluded from the output.
    """
    from tscode_kg.coderank import (  # noqa: PLC0415
        build_code_graph,
        compute_coderank,
        rank_query_hybrid,
        rank_query_ppr,
    )

    kg = _get_kg()
    db_path = str(kg.db_path)
    rel_list = [r.strip() for r in rels.split(",") if r.strip()]

    # Get semantic seeds from the vector index
    try:
        raw = kg.query(q, k=k, hop=0, rels=tuple(rel_list))
        seed_data = json.loads(raw.to_json())
        seed_nodes = seed_data.get("nodes", [])
        semantic_scores: dict[str, float] = {
            n["id"]: float((n.get("relevance") or {}).get("score", 0.0))
            for n in seed_nodes
            if (n.get("relevance") or {}).get("score", 0.0) > 0
        }
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"Seed retrieval failed: {exc}"}, indent=2)

    if not semantic_scores:
        return json.dumps({"error": "No semantic seeds found for query."}, indent=2)

    try:
        graph = build_code_graph(
            db_path,
            include_relations=rel_list,
            exclude_test_paths=exclude_tests,
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"Graph build failed: {exc}"}, indent=2)

    global_cr = compute_coderank(graph)
    try:
        if mode == "ppr":
            results = rank_query_ppr(graph, semantic_scores, radius=radius, top_k=top)
        else:
            results = rank_query_hybrid(
                graph, semantic_scores, global_coderank=global_cr, radius=radius, top_k=top
            )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"Ranking failed: {exc}"}, indent=2)

    output = []
    for rank_idx, r in enumerate(results, start=1):
        if r.node_id.startswith("sym:"):
            continue
        output.append(
            {
                "rank": rank_idx,
                "node_id": r.node_id,
                "adjusted_score": round(r.adjusted_score, 6),
                "final_score": round(r.final_score, 6),
                "semantic_score": round(r.semantic_score, 6),
                "centrality_score": round(r.centrality_score, 6),
                "proximity_score": round(r.proximity_score, 6),
                "kind": r.kind,
                "qualname": r.qualname,
                "module_path": r.module_path,
                "why": list(r.why),
            }
        )

    return json.dumps(
        {"query": q, "mode": mode, "returned": len(output), "results": output},
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
def explain_rank(node_id: str, q: str = "") -> str:
    """
    Explain the CodeRank score components for a specific node.

    Returns a Markdown report showing the node's structural position in the
    graph: how many nodes call it, import it, or inherit from / implement /
    extend it; its global CodeRank score; and, when a query is provided, its
    semantic relevance and proximity to the query seed set.

    :param node_id: Stable node identifier, e.g.
                    ``fn:src/utils/helpers.ts:formatDate``.
    :param q: Optional query string.  When provided, semantic score and
              proximity to the query seed set are included in the report.
    :return: Markdown-formatted explanation of the node's rank components.
    """
    from tscode_kg.coderank import (  # noqa: PLC0415
        DEFAULT_GLOBAL_RELS,
        build_code_graph,
        compute_coderank,
        compute_seed_proximity,
    )

    kg = _get_kg()
    db_path = str(kg.db_path)

    node = kg.node(node_id)
    if node is None:
        return f"## Node Not Found\n\nNode ID `{node_id}` does not exist."

    kind = node.get("kind", "unknown")
    name = node.get("qualname") or node.get("name", "unknown")
    out: list[str] = [f"## CodeRank Explanation: `{name}` ({kind})\n"]
    out.append(f"- **ID:** `{node_id}`")
    if node.get("module_path"):
        out.append(f"- **Module:** `{node['module_path']}`")
    out.append("")

    # Build graph and compute global CodeRank
    try:
        graph = build_code_graph(
            db_path,
            include_relations=list(DEFAULT_GLOBAL_RELS),
            exclude_test_paths=True,
        )
        scores = compute_coderank(graph)
    except Exception as exc:  # noqa: BLE001
        return f"## Error\n\nFailed to build graph: `{exc}`"

    global_score = scores.get(node_id, 0.0)
    meaningful_scores = sorted(
        (v for k, v in scores.items() if not k.startswith("sym:")), reverse=True
    )
    rank_pos = next(
        (i + 1 for i, s in enumerate(meaningful_scores) if s <= global_score),
        len(meaningful_scores),
    )

    out.append("### Global CodeRank\n")
    out.append(f"- **Score:** `{global_score:.8f}`")
    out.append(f"- **Rank:** #{rank_pos} of {len(meaningful_scores)} meaningful nodes")
    out.append("")

    # Structural context from graph
    if node_id in graph:
        in_edges = list(graph.in_edges(node_id, data=True))
        out.append("### Structural Inbound Edges\n")
        callers_count = sum(1 for _, _, d in in_edges if "CALLS" in d.get("relations", set()))
        importers_count = sum(1 for _, _, d in in_edges if "IMPORTS" in d.get("relations", set()))
        inheritors_count = sum(
            1
            for _, _, d in in_edges
            if d.get("relations", set()) & {"INHERITS", "IMPLEMENTS", "EXTENDS"}
        )
        if callers_count:
            out.append(f"- Called by **{callers_count}** upstream node(s)")
        if importers_count:
            out.append(f"- Imported by **{importers_count}** upstream node(s)")
        if inheritors_count:
            out.append(
                f"- Inherited/implemented/extended by **{inheritors_count}** downstream node(s)"
            )
        if not (callers_count or importers_count or inheritors_count):
            out.append("- No inbound structural edges found in the ranked graph")
        out.append("")

        out_edges = list(graph.out_edges(node_id, data=True))
        if out_edges:
            out.append("### Structural Outbound Edges\n")
            out.append(f"- Calls/imports/inherits **{len(out_edges)}** downstream node(s)")
            out.append("")

    # Optional query-conditioned scores
    if q:
        out.append("### Query-Conditioned Scores\n")
        try:
            raw = kg.query(q, k=8, hop=0)
            seed_data = json.loads(raw.to_json())
            seed_nodes = seed_data.get("nodes", [])
            semantic_scores: dict[str, float] = {
                n["id"]: float((n.get("relevance") or {}).get("score", 0.0)) for n in seed_nodes
            }
            this_semantic = semantic_scores.get(node_id, 0.0)
            out.append(f"- **Query:** `{q}`")
            out.append(f"- **Semantic score:** `{this_semantic:.4f}`")

            if node_id in graph:
                seeds = list(semantic_scores.keys())
                proximity = compute_seed_proximity(graph, seeds)
                prox = proximity.get(node_id, 0.0)
                out.append(f"- **Proximity to seeds:** `{prox:.4f}`")
                if prox >= 1.0:
                    out.append("  → Direct semantic seed")
                elif prox >= 0.5:
                    out.append("  → One hop from a semantic seed")
                elif prox > 0:
                    out.append("  → Within local query neighborhood")
                else:
                    out.append("  → Outside query neighborhood")
        except Exception as exc:  # noqa: BLE001
            out.append(f"- Query scoring failed: `{exc}`")
        out.append("")

    out.append("---\n")
    out.append(
        "*Use `rank_nodes()` for global top-N ranking, or `query_ranked()` for query-conditioned ranking.*"
    )
    return "\n".join(out)


@mcp.tool()
def snapshot_list(limit: int = 10, branch: str = "") -> str:
    """
    List saved temporal snapshots of codebase metrics in reverse chronological order.

    Each entry in the returned list contains a ``key`` (tree hash snapshot
    identifier), ``branch``, ``timestamp``, ``version``, and a summary of
    key metrics (node count, edge count, JSDoc coverage) plus deltas vs. the
    previous snapshot.  Use the ``key`` field when calling ``snapshot_show()``
    or ``snapshot_diff(key_a=..., key_b=...)``.

    Use this tool to answer questions like "how has the codebase grown?" or
    "when did JSDoc coverage improve?" or "show me only main-branch snapshots".

    :param limit: Maximum number of snapshots to return (default 10; pass 0 for all).
    :param branch: If provided, filter to snapshots from this branch only
                   (e.g. ``"main"`` or ``"develop"``).
    :return: JSON array of snapshot metadata dicts, most recent first.
    """
    mgr = _get_snapshot_mgr()
    snapshots = mgr.list_snapshots(
        limit=limit if limit > 0 else None,
        branch=branch if branch else None,
    )
    for snap in snapshots:
        snap_metrics = snap.get("metrics", {})
        snap["freshness"] = _snapshot_freshness(snap_metrics.get("total_nodes", 0))
    return json.dumps(snapshots, indent=2, ensure_ascii=False)


@mcp.tool()
def snapshot_show(key: str = "latest") -> str:
    """
    Show full details of a specific codebase metrics snapshot.

    Pass a snapshot key (tree hash) to retrieve that exact snapshot, or use
    the special value ``"latest"`` (default) to retrieve the most recent one.

    Snapshot keys are the ``key`` field returned by ``snapshot_list()``.

    The returned object contains the full metrics dict (total_nodes,
    total_edges, meaningful_nodes, docstring_coverage, node_counts,
    edge_counts, critical_issues, complexity_median), the top hotspots, and
    deltas computed vs. both the previous and the baseline (oldest) snapshots.

    :param key: Snapshot key to load, or ``"latest"`` for the most
                recent snapshot (default ``"latest"``).  Keys are tree
                hashes returned by ``snapshot_list()``.
    :return: JSON object with full snapshot details, or an error dict if
             the requested snapshot does not exist.
    """
    mgr = _get_snapshot_mgr()

    if key == "latest":
        entries = mgr.list_snapshots(limit=1)
        if not entries:
            return json.dumps({"error": "No snapshots found."})
        key = entries[0]["key"]

    snapshot = mgr.load_snapshot(key)
    if snapshot is None:
        return json.dumps({"error": f"Snapshot not found for key: {key!r}"})
    out = snapshot.to_dict()
    out["freshness"] = _snapshot_freshness(snapshot.metrics.get("total_nodes", 0))
    return json.dumps(out, indent=2, ensure_ascii=False)


@mcp.tool()
def snapshot_diff(key_a: str, key_b: str) -> str:
    """
    Compare two codebase metric snapshots side-by-side.

    Returns the full metrics dict for both snapshots and a computed delta
    (b − a) covering node and edge counts, plus per-kind node count and
    per-relation edge count deltas.

    Typical workflow::

        # 1. List available snapshots — note the 'key' field in each entry
        snapshot_list()

        # 2. Diff any two using the key= field values
        snapshot_diff(key_a="abc1234ef...", key_b="def5678ab...")

    :param key_a: First (older) snapshot key — the ``key`` field from
                  ``snapshot_list()`` output (a tree-hash string).
    :param key_b: Second (newer) snapshot key — the ``key`` field from
                  ``snapshot_list()`` output (a tree-hash string).
    :return: JSON object with keys ``a`` (metrics + issues list for key_a),
             ``b`` (metrics + issues list for key_b), ``delta`` (b − a),
             ``node_counts_delta``, and ``edge_counts_delta``. Returns an
             error dict if either snapshot is missing.
    """
    mgr = _get_snapshot_mgr()
    result = mgr.diff_snapshots(key_a, key_b)
    if "error" not in result:
        result["freshness"] = {
            "a": _snapshot_freshness(result.get("a", {}).get("metrics", {}).get("total_nodes", 0)),
            "b": _snapshot_freshness(result.get("b", {}).get("metrics", {}).get("total_nodes", 0)),
        }
    return json.dumps(result, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="tscodekg-mcp",
        description="TypeScriptKG MCP server — exposes TS/JS codebase query tools to AI agents.",
    )
    p.add_argument("--repo", default=".", help="Repository root directory (default: .)")
    p.add_argument(
        "--db",
        default=".tscodekg/graph.sqlite",
        help="Path to the SQLite knowledge graph",
    )
    p.add_argument(
        "--vectors",
        default=".tscodekg/vectors.sqlite",
        help="Path to the sqlite-vec vector store",
    )
    p.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Sentence-transformer model name (default: {DEFAULT_MODEL})",
    )
    p.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="MCP transport: stdio (default) or sse (HTTP)",
    )
    return p.parse_args(argv)


def main(argv: list | None = None) -> None:
    """CLI entry point for the TypeScriptKG MCP server."""
    global _kg, _snapshot_mgr

    args = _parse_args(argv)

    repo = Path(args.repo).resolve()
    db = Path(args.db) if Path(args.db).is_absolute() else repo / args.db
    vectors = Path(args.vectors) if Path(args.vectors).is_absolute() else repo / args.vectors

    if not db.exists():
        print(
            f"WARNING: SQLite database not found at '{db}'.\nRun 'tscodekg build --repo .' first.",
            file=sys.stderr,
        )

    print(
        f"TypeScriptKG MCP server starting\n"
        f"  repo     : {repo}\n"
        f"  db       : {db}\n"
        f"  vectors  : {vectors}\n"
        f"  model    : {args.model}\n"
        f"  transport: {args.transport}",
        file=sys.stderr,
    )

    _kg = TypeScriptKG(repo_root=repo, db_path=db, vectors_path=vectors, model=args.model)
    _snapshot_mgr = SnapshotManager(repo / ".tscodekg" / "snapshots", db_path=db)
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
