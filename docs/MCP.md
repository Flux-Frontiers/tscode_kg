# TypeScriptKG MCP Reference

**Tool reference and query strategy for the TypeScriptKG MCP server**

*Author: Eric G. Suchanek, PhD*

---

## Overview

TypeScriptKG ships a built-in MCP server (`tscodekg mcp`) that exposes the full hybrid query and snippet-pack pipeline as structured tools consumable by any MCP-compatible AI agent — Claude Code, Claude Desktop, Cursor, Continue, GitHub Copilot, or Kilo Code.

Once configured, the agent gains twenty tools, grouped by purpose. `stats`, `query`, `pack`, `get_node` and `neighbors` are the fleet's canonical tools, named the same on every KG server; the other fifteen are TypeScriptKG's own. `tscodekg mcp --manifest` prints the live list, with every parameter, as JSON without opening the graph.

**Discovery & exploration**

| Tool | Purpose |
|---|---|
| `stats()` | Codebase size and shape — good first call |
| `query(q)` | Semantic + structural graph exploration |
| `pack(q)` | Source-grounded code snippets for implementation detail |
| `get_node(node_id)` | Single node metadata |
| `neighbors(node_id, rels, direction, limit)` | A node's one-hop edges and the nodes at their far ends |
| `list_nodes(module_path, kind)` | List nodes filtered by module path prefix and/or kind |
| `find_node(name, kind)` | Search nodes by (partial) name when you don't know the stable ID |
| `find_definition_at(file, line)` | Reverse-lookup the node spanning a `file:line` location |

**Relationships & analysis**

| Tool | Purpose |
|---|---|
| `callers(node_id, rel, paths)` | Precise fan-in lookup — resolves through `sym:` stubs |
| `explain(node_id)` | Natural-language explanation: role, JSDoc, callers, callees |
| `analyze_repo()` | Structural analysis: node/edge counts, JSDoc coverage, distribution |

**Centrality & ranking**

| Tool | Purpose |
|---|---|
| `centrality(top, kinds, group_by)` | SIR-weighted PageRank — most structurally important nodes/modules |
| `bridge_centrality(top, include_imports)` | Module connectivity — orchestrator/hub identification |
| `framework_nodes(top)` | Hub modules combining high SIR + high connectivity |
| `rank_nodes(top, rels, persist_metric, exclude_tests)` | Global CodeRank PageRank with optional persistence |
| `query_ranked(q, mode, k, top, rels, radius, exclude_tests)` | Query + hybrid/PPR ranking with explainability |
| `explain_rank(node_id, q)` | Explain a node's CodeRank score components |

**Temporal snapshots**

| Tool | Purpose |
|---|---|
| `snapshot_list(limit, branch)` | List saved codebase snapshots in reverse chronological order |
| `snapshot_show(key)` | Full metrics for a specific snapshot (or `"latest"`) |
| `snapshot_diff(key_a, key_b)` | Compare two snapshots side-by-side with computed deltas |

> **Setup is covered separately.** For installing `tscode-kg`, building the graph, and configuring Claude Code / Claude Desktop / Kilo Code / GitHub Copilot / Cline, see **[INSTALLATION.md](INSTALLATION.md)**. This document picks up *after* the server is running.

---

## Smoke Test

Verify the pipeline end-to-end before wiring the server into an agent:

```bash
# Sample query against the built graph
tscodekg query "module structure"
```

Or call TypeScriptKG directly from Python:

```bash
python -c "
from tscode_kg import TypeScriptKG
import json
kg = TypeScriptKG(repo_root='.', db_path='.tscodekg/graph.sqlite', vectors_path='.tscodekg/vectors.sqlite')
print(json.dumps(kg.stats(), indent=2))
"
```

Expected output shape:

```json
{
  "kind": "code",
  "nodes": {
    "total": 352,
    "by_kind": { "module": 18, "class": 12, "interface": 25, "function": 201, "method": 96 }
  },
  "edges": {
    "total": 1087,
    "by_rel": { "CONTAINS": 378, "CALLS": 512, "IMPORTS": 147, "IMPLEMENTS": 30, "EXTENDS": 20 }
  },
  "meaningful_nodes": 352,
  "docstring_coverage": 0.62,
  "db_path": ".tscodekg/graph.sqlite",
  "vector_backend": "sqlite-vec"
}
```

This is the fleet's stats shape, the same on every KG server: `nodes` and `edges` with a `total` and a breakdown, and TypeScriptKG's own measures (`meaningful_nodes`, `docstring_coverage`, ...) beside them.

If this succeeds, the MCP server will work correctly.

---

## Tool Reference

### `stats()`

Return node and edge counts broken down by kind and relation, plus JSDoc coverage.

**When to use:** First call in any session — understand the codebase size and shape before querying.

**Parameters:** None.

**Returns:** JSON in the fleet's stats shape (see the smoke test above): `kind`, `nodes.total` and `nodes.by_kind`, `edges.total` and `edges.by_rel`, plus meaningful nodes (excluding `sym:` stubs), JSDoc coverage (fraction of functions/methods with JSDoc comments) and the database path. Reads the graph only; never loads the embedding model.

---

### `query(q, k, hop, rels, max_nodes, min_score, max_per_module, rerank_mode, ...)`

Hybrid semantic + structural query. Returns ranked nodes and edges.

**When to use:** Exploring the graph — finding what classes, interfaces, functions, and modules are relevant to a topic, understanding call relationships, tracing imports.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `q` | `str` | — | Natural-language query |
| `k` | `int` | `8` | Semantic seed count (top-K from vector search) |
| `hop` | `int` | `1` | Graph expansion hops from each seed |
| `rels` | `list[str]` | all six | Edge types to follow, e.g. `["CALLS", "IMPLEMENTS"]`; omit for CONTAINS, CALLS, IMPORTS, INHERITS, IMPLEMENTS, EXTENDS |
| `max_nodes` | `int` | `25` | Maximum nodes to return |
| `min_score` | `float` | `0.0` | Minimum seed score in `[0, 1]` |
| `max_per_module` | `int` | `3` | Maximum returned nodes per module (`0` disables the cap) |
| `rerank_mode` | `str` | `"hybrid"` | `hybrid` (70% vector + 30% lexical), `semantic`, or `legacy` |
| `rerank_semantic_weight` | `float` | `0.7` | Semantic weight for `hybrid` mode |
| `rerank_lexical_weight` | `float` | `0.3` | Lexical weight for `hybrid` mode |

**Returns:** JSON with keys: `query`, `seeds`, `expanded_nodes`, `returned_nodes`, `hop`, `rels`, `nodes`, `edges`.

---

### `pack(q, k, hop, rels, context, max_lines, max_nodes, min_score, max_per_module, rerank_mode, ...)`

Hybrid query + source-grounded snippet extraction. Returns a Markdown context pack.

**When to use:** Any time you need to read actual source code — understanding an implementation, debugging, writing tests, reviewing logic. **Prefer this over `query` when implementation details matter.**

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `q` | `str` | — | Natural-language query |
| `k` | `int` | `8` | Semantic seed count |
| `hop` | `int` | `1` | Graph expansion hops |
| `rels` | `list[str]` | all six | Edge types to follow; omit for all six |
| `context` | `int` | `5` | Extra context lines around each definition |
| `max_lines` | `int` | `60` | Maximum lines per snippet block |
| `max_nodes` | `int` | `15` | Maximum nodes in the pack |
| `min_score` | `float` | `0.0` | Minimum seed score in `[0, 1]` |
| `max_per_module` | `int` | `3` | Maximum returned nodes per module (`0` disables the cap) |
| `rerank_mode` | `str` | `"hybrid"` | `hybrid`, `semantic`, or `legacy` |

**Returns:** Markdown string with ranked, deduplicated code snippets and line numbers.

---

### `get_node(node_id)`

Fetch a single node by its stable ID.

**When to use:** You have a node ID from a previous query result and want its full metadata. Follow with `neighbors(node_id)` for its edges.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `node_id` | `str` | — | Stable node ID, e.g. `cls:src/auth/middleware.ts:AuthMiddleware` |

**Node ID format:** `<kind>:<module_path>:<qualname>`

| Prefix | Kind |
|---|---|
| `mod:` | module |
| `cls:` | class |
| `iface:` | interface |
| `type:` | type alias |
| `enum:` | enum |
| `ns:` | namespace |
| `fn:` | function |
| `meth:` | method |
| `sym:` | unresolved external import stub |

**Returns:** JSON with the node's id, kind, name, qualname, module path, line span and JSDoc. An unknown ID is a tool error ("no node with id ...").

---

### `neighbors(node_id, rels, direction, limit)`

A node's one-hop neighborhood: its edges and the nodes at their far ends. Replaces `get_node(include_edges=True)`.

**When to use:** After `get_node`, to see what a node contains, calls, imports, implements or extends, and what points at it. Reads the graph only, so it never loads the embedding model.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `node_id` | `str` | — | Stable node ID |
| `rels` | `list[str]` | all | Edge types to follow, e.g. `["CALLS"]`; omit for every relation |
| `direction` | `str` | `"both"` | `"out"` (edges from the node), `"in"` (edges to it) or `"both"` |
| `limit` | `int` | `50` | Most edges to return (1-500) |

**Returns:** JSON with the node, its edges and the far-end nodes. An unknown ID is a tool error. For callers resolved through `sym:` import stubs, use `callers(node_id)`.

---

### `list_nodes(module_path, kind)`

List nodes filtered by module path prefix and/or kind.

**When to use:** Enumerating the contents (classes, interfaces, functions) of a specific module before inspecting individual nodes with `get_node`.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `module_path` | `str` | `""` | Module path prefix filter, e.g. `src/auth/middleware.ts` |
| `kind` | `str` | `""` | Node kind filter: `module` / `class` / `interface` / `type_alias` / `enum` / `namespace` / `function` / `method` |

**Returns:** JSON array of matching node dicts (`sym:` stubs excluded).

---

### `find_node(name, kind)`

Search graph nodes by name (or qualname) without knowing the full stable ID.

**When to use:** You saw a function, class, or interface name in a stack trace, log line, or user question and don't yet have its node ID. Once you have the ID, pass it to `get_node`, `explain`, or `callers`.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | — | Function, class, or interface name. Case-insensitive match against `name` and `qualname` |
| `kind` | `str` | `""` | Optional kind filter: `module` / `class` / `interface` / `function` / `method` / etc. Empty matches all |

**Returns:** JSON array of matching node dicts (`id`, `name`, `qualname`, `kind`, `module_path`, `lineno`, truncated JSDoc). Empty array when no match.

---

### `find_definition_at(file, line)`

Reverse-resolve a `(file, line)` pair to the innermost node spanning that location.

**When to use:** You're reading a file in an IDE and want to understand the symbol at a specific line without manually constructing a node ID. Returns the same Markdown report as `explain()`.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `file` | `str` | Module path as stored in the graph, e.g. `src/auth/middleware.ts`. Leading `./` is stripped |
| `line` | `int` | 1-indexed line number within the file |

**Returns:** Markdown explanation from `explain()` for the innermost function / method / class whose `lineno ≤ line ≤ end_lineno`, falling back to the module node when no narrower match exists. Informative error if no node spans the location.

---

### `callers(node_id, rel, paths)`

Find all callers of a specific node by inverting a relation — fan-in analysis.

**When to use:** Finding all callers of a specific function/method/class. More precise than `query` for this use case because it resolves cross-module callers through `sym:` import stubs.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `node_id` | `str` | — | Stable node ID, e.g. `fn:src/utils/helpers.ts:formatDate` |
| `rel` | `str` | `"CALLS"` | Relation type to invert — e.g. `INHERITS` for subclasses, `IMPLEMENTS` for implementations, `IMPORTS` for importers |
| `paths` | `str` | `""` | Comma-separated module path prefixes to include, e.g. `"src/"` to exclude test callers. Empty returns all |

**Returns:** JSON with `node_id`, `rel`, `caller_count`, `callers` (list of node dicts).

**Example return shape:**

```json
{
  "node_id": "fn:src/utils/helpers.ts:formatDate",
  "rel": "CALLS",
  "caller_count": 7,
  "callers": [
    { "id": "meth:src/report/render.ts:ReportRenderer.header", "kind": "method", ... }
  ]
}
```

> **Note:** `sym:` nodes are resolved automatically — callers from other modules that import the target function are included even when they reference it via an alias.

---

### `explain(node_id)`

Return a natural-language Markdown explanation of a single code node.

**When to use:** You want to understand what a specific function, method, class, or interface does — its role, who calls it, what it calls — without reading the raw source. Use as the first step when a user asks about a specific node before reaching for `pack`.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `node_id` | `str` | Stable node ID, e.g. `fn:src/utils/helpers.ts:formatDate` |

**Returns:** Markdown report with: kind and qualified name, module path and line range, full JSDoc, list of callers (top 10), list of callees, and a role assessment based on call count.

---

### `analyze_repo()`

Run a full structural analysis of the indexed TypeScript/JavaScript repository.

**When to use:** When you want a comprehensive health check or architectural overview — node/edge counts, JSDoc coverage, node distribution by kind, and edge distribution by relation.

**Parameters:** None.

**Returns:** Markdown-formatted analysis report. For the richer 14-phase report (fan-in/out, coupling, CodeRank, SIR, hierarchy), run `tscodekg analyze` from the CLI — see [Analyze.md](Analyze.md).

---

### `centrality(top, kinds, group_by)`

Run Structural Importance Ranking (SIR) — a deterministic weighted PageRank over the `sym`-resolved call graph.

**When to use:** Identify the most structurally critical nodes or modules — high-leverage refactor targets, candidates for tighter test coverage, the de-facto "core" of the codebase. Edge weights favor `CALLS` > `INHERITS`/`IMPLEMENTS` > `IMPORTS` > `CONTAINS`, with cross-module amplification and a private-symbol penalty.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `top` | `int` | `20` | Maximum ranked entries to return |
| `kinds` | `str` | `""` | Comma-separated kinds: `module,class,interface,function,method`. Empty = all. Ignored when `group_by="module"` |
| `group_by` | `str` | `"node"` | `"node"` for individual rankings; `"module"` aggregates per module |

**Returns:** Markdown ranking table with score, inbound edge count, and cross-module inbound count. Scores are normalized to sum to 1.0.

---

### `bridge_centrality(top, include_imports)`

Compute module connectivity — how many unique modules each module interacts with. Replaces betweenness centrality (meaningless when inter-module edges are zero).

**When to use:** Find orchestrator and hub modules in well-modularized codebases. Connectivity score = (unique callers + unique callees) / 30 + frequency / 50. Persists scores to the `centrality_scores` table for `framework_nodes()`.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `top` | `int` | `20` | Number of top connectivity modules to return |
| `include_imports` | `bool` | `true` | Include `IMPORTS` edges in the connectivity calculation |

**Returns:** Markdown ranking table of modules by connectivity score.

---

### `framework_nodes(top)`

Identify framework-like (hub) modules using `0.6 × normalized SIR + 0.4 × normalized connectivity`. Auto-runs `centrality()` and `bridge_centrality()` on first call if not already persisted.

**When to use:** Find modules that are *both* structurally central *and* highly connected — architecturally critical hubs (orchestrators, framework cores) rather than just popular utilities.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `top` | `int` | `20` | Number of top framework-like modules to return |

**Returns:** Markdown ranking table of framework nodes with composite score.

---

### `rank_nodes(top, rels, persist_metric, exclude_tests)`

Compute global weighted CodeRank (PageRank) over the repository graph.

**When to use:** Independent CodeRank scoring with persistence — useful for periodic baseline measurements, dashboards, or feeding ranking metrics into other tools. Default relation weights: `CALLS=1.0, IMPORTS=0.9, INHERITS=0.75` (with `IMPLEMENTS` and `EXTENDS` also at `0.75`).

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `top` | `int` | `25` | Number of top-ranked nodes to return |
| `rels` | `str` | `"CALLS,IMPORTS,INHERITS"` | Comma-separated relations to include in the graph |
| `persist_metric` | `str` | `""` | If non-empty, persist scores to `node_metrics` under this metric name (e.g. `"coderank_global"`) |
| `exclude_tests` | `bool` | `true` | Exclude test-path nodes from the graph |

**Returns:** JSON array of ranked node dicts: `node_id`, `score`, `top_pct` (e.g. `"top 0.5%"`), `kind`, `qualname`, `module_path`, `rank`. `sym:` stubs are excluded.

---

### `query_ranked(q, mode, k, top, rels, radius, exclude_tests)`

Rank query results using CodeRank-enhanced hybrid or personalized PageRank — a more explainable alternative to `query` when you care *why* a result ranked highly.

**When to use:** Search where ranking transparency matters. Two modes:

- `hybrid` (default): `0.60 × semantic + 0.25 × centrality + 0.15 × proximity`
- `ppr`: `0.70 × personalized PageRank + 0.30 × semantic`

Each result includes a `why` string explaining the score components. `sym:` stub nodes are always excluded.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `q` | `str` | — | Natural-language query |
| `mode` | `str` | `"hybrid"` | `"hybrid"` or `"ppr"` |
| `k` | `int` | `8` | Semantic seed count |
| `top` | `int` | `25` | Maximum ranked results to return |
| `rels` | `str` | `"CALLS,IMPORTS,INHERITS"` | Relations to include in the local graph |
| `radius` | `int` | `2` | Graph expansion radius around seeds |
| `exclude_tests` | `bool` | `true` | Exclude test-path nodes |

**Returns:** JSON array of ranked result dicts with score components and `why` explanation strings.

---

### `explain_rank(node_id, q)`

Explain the CodeRank score components for a specific node.

**When to use:** A node turned up in a ranked result and you want to understand *why* — how many nodes call/import/inherit from it, its global CodeRank, and (with `q`) its semantic relevance and proximity to the query seed set.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `node_id` | `str` | — | Stable node identifier, e.g. `fn:src/utils/helpers.ts:formatDate` |
| `q` | `str` | `""` | Optional query. When provided, semantic score and proximity to the seed set are included |

**Returns:** Markdown report of the node's rank components.

---

### `snapshot_list(limit, branch)`

List saved temporal snapshots of codebase metrics in reverse chronological order.

**When to use:** Tracking how the codebase has grown over time — node/edge counts, JSDoc coverage changes, critical issue trends. Returns the `key` values needed for `snapshot_show` and `snapshot_diff`.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `limit` | `int` | `10` | Maximum snapshots to return; pass `0` for all |
| `branch` | `str` | `""` | Filter to snapshots from a specific branch; omit or pass `""` for all |

**Returns:** JSON array of snapshot metadata (key, branch, timestamp, version, key metrics, deltas vs. previous, and a `freshness` block comparing each snapshot's node count against the live graph).

---

### `snapshot_show(key)`

Show full details of a specific codebase metrics snapshot.

**When to use:** Inspecting the state of the codebase at a specific snapshot — full node/edge counts, JSDoc coverage, hotspots, and deltas vs. both the previous and baseline snapshots.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `key` | `str` | `"latest"` | Snapshot key -- a release tag, a UTC timestamp for an untagged capture, or `"latest"` for the most recent |

**Returns:** JSON object with the full metrics dict (`total_nodes`, `total_edges`, `meaningful_nodes`, `docstring_coverage`, `node_counts`, `edge_counts`, `critical_issues`, `complexity_median`), top hotspots, deltas, and freshness vs. the live graph.

---

### `snapshot_diff(key_a, key_b)`

Compare two codebase metric snapshots side-by-side.

**When to use:** Quantifying the impact of a refactor, release, or sprint — how many nodes were added, did coverage improve, did critical issues increase?

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `key_a` | `str` | First (older) snapshot key (a release tag or timestamp, not a tree hash) |
| `key_b` | `str` | Second (newer) snapshot key (a release tag or timestamp, not a tree hash) |

**Returns:** JSON with keys `a` (metrics for `key_a`), `b` (metrics for `key_b`), `delta` (b − a), `node_counts_delta`, and `edge_counts_delta`, plus per-snapshot freshness.

**Typical workflow:**

```
1. snapshot_list()                         → discover available snapshot keys
2. snapshot_diff("abc1234", "def5678")     → compare two points in time
```

---

## Query Strategy Guide

### Choosing `k` and `hop`

| Goal | Recommended settings |
|---|---|
| Narrow, precise lookup | `k=4, hop=0` — seeds only, no expansion |
| Standard exploration | `k=8, hop=1` — default; good for most queries |
| Broad context sweep | `k=12, hop=2` — pulls in more of the call graph |
| Deep dependency trace | `k=8, hop=2, rels=["CALLS", "IMPORTS"]` — follow execution paths |

Higher `hop` values expand the result set geometrically. Use `max_nodes` in `pack` to keep output manageable.

### Choosing `rels`

| Relation | Meaning | When to include |
|---|---|---|
| `CONTAINS` | Module contains a class/function/interface | Almost always — provides structural context |
| `CALLS` | Function A calls function B | Tracing execution flow, finding callers/callees |
| `IMPORTS` | Module A imports from module B | Dependency analysis |
| `INHERITS` | Class A extends class B | OOP hierarchy exploration |
| `IMPLEMENTS` | Class A implements interface B | Contract/implementation mapping |
| `EXTENDS` | Interface A extends interface B | Type hierarchy exploration |

### Typical agent workflow

```
1. stats()
   → understand codebase size and shape

2. query("authentication middleware", k=8, hop=1)
   → identify relevant classes and functions, note their IDs

3. explain("cls:src/auth/middleware.ts:AuthMiddleware")
   → natural-language orientation before reading source

4. pack("JWT token validation", k=6, hop=1)
   → read the actual implementation

5. get_node("meth:src/auth/middleware.ts:AuthMiddleware.verify")
   neighbors("meth:src/auth/middleware.ts:AuthMiddleware.verify")
   -> fetch node metadata, then its edges and the nodes at their far ends

6. pack("token validation error handling", k=4, hop=2, rels=["CALLS"])
   → follow the call graph deeper into error paths

7. snapshot_list()
   → review how the codebase has evolved over time
   snapshot_diff("abc1234", "def5678")
   → compare metrics between two commits
```

### When to reach for the ranking tools

| Situation | Tool |
|---|---|
| User asked about a name from a stack trace or chat — no node ID | `find_node(name)` |
| User pointed at a file and a line number in their editor | `find_definition_at(file, line)` |
| You need to know "what's actually important in this codebase?" | `centrality()` or `framework_nodes()` |
| You need explainable search results with score components | `query_ranked(q)` instead of `query(q)` |
| A ranked result surprised you — why did this node rank so high? | `explain_rank(node_id, q)` |
| You want a persisted CodeRank baseline for dashboards / regression checks | `rank_nodes(persist_metric="coderank_global")` |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Empty results from `query` | sqlite-vec index missing or stale | `tscodekg build --index-only` |
| Node IDs in results don't resolve with `get_node` | Graph rebuilt since last query | `tscodekg build`; restart the MCP server |
| Snippets show wrong line numbers | Source files changed since build | `tscodekg build` |
| MCP server not appearing in agent | Wrong/relative paths in MCP config, or agent not restarted | See [INSTALLATION.md § MCP Server Setup](INSTALLATION.md#mcp-server-setup) — all paths must be absolute |
| `tscodekg` command not found | Package not installed or venv not active | `pip install tscode-kg`, or use the absolute venv path |
| Session refused with `tscodekg: no graph at ...` | Graph never built for this repo, or `--repo`/`--db` point elsewhere | `tscodekg build --repo .` first, or fix the paths |

For installation, build, and per-agent config issues see [INSTALLATION.md](INSTALLATION.md).

---

## Summary

| Concern | Answer |
|---|---|
| What does the MCP server expose? | 20 tools across discovery (`stats`, `query`, `pack`, `get_node`, `neighbors`, `list_nodes`, `find_node`, `find_definition_at`), relationships (`callers`, `explain`, `analyze_repo`), centrality & ranking (`centrality`, `bridge_centrality`, `framework_nodes`, `rank_nodes`, `query_ranked`, `explain_rank`), and snapshots (`snapshot_list`, `snapshot_show`, `snapshot_diff`) |
| What must exist before starting? | `.tscodekg/graph.sqlite` + `.tscodekg/vectors.sqlite` |
| How do I build those? | `tscodekg build` (or `--graph-only` then `--index-only`) — see [INSTALLATION.md](INSTALLATION.md) |
| Is the server stateful? | Yes — one `TypeScriptKG` instance per client session, opened when the session starts and closed when it ends |
| Can it modify the graph? | No — strictly read-only |
| Which tool should I call first? | `stats()` for orientation |
| How do I automate setup? | `tscodekg init --repo .` — see [INSTALLATION.md](INSTALLATION.md) |
