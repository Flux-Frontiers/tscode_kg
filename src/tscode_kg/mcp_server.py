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

analyze_repo()
    Run structural analysis and return a Markdown report.

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

# ---------------------------------------------------------------------------
# Global state — initialised in main()
# ---------------------------------------------------------------------------

_kg: TypeScriptKG | None = None


def _get_kg() -> TypeScriptKG:
    if _kg is None:
        raise RuntimeError(
            "TypeScriptKG not initialised. Run the server via 'tscodekg-mcp --repo /path/to/repo'"
        )
    return _kg


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
        "**analyze_repo()** — Structural analysis: node counts, edge counts, JSDoc coverage, "
        "node distribution by kind.\n\n"
        "## Recommended Workflows\n\n"
        "- **Explore unfamiliar TS/JS repo**: graph_stats → query_codebase → pack_snippets\n"
        "- **Find a specific class/function**: find_node(name) → get_node(include_edges=True)\n"
        "- **Understand an interface**: get_node → pack_snippets\n"
        "- **Trace usage of a symbol**: find_node(name) → callers(node_id)\n"
        "- **Identify structural hotspots**: centrality(top=20) or centrality(group_by='module')\n"
        "- **Architecture review**: analyze_repo\n"
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
def analyze_repo() -> str:
    """
    Run a full structural analysis of the indexed TypeScript/JavaScript repository.

    Returns node/edge counts, JSDoc coverage, node distribution by kind, and
    edge distribution by relation.

    :return: Markdown-formatted analysis report.
    """
    return _get_kg().analyze()


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
    global _kg

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
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
