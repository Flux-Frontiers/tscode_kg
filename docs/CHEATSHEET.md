# TypeScriptKG Query Cheatsheet

A practical reference for the twenty MCP tools, with examples for TypeScript/JavaScript codebases.
All queries below work against a built TypeScriptKG knowledge graph.

---

## The Twenty Tools at a Glance

### Core Tools

| Tool | Best for | Returns |
|---|---|---|
| `stats()` | Orientation — size and shape of the graph | JSON: node/edge counts by kind |
| `query(q)` | Structural exploration — *what exists, how things relate* | JSON: ranked nodes + edges |
| `pack(q)` | Implementation detail — *actual source code* | Markdown: snippets with line numbers |
| `get_node(node_id)` | Pinpoint lookup — one node by its stable ID | JSON: full node metadata |
| `neighbors(node_id, rels, direction, limit)` | Immediate neighborhood -- a node's edges and far-end nodes | JSON: node, edges, nodes |
| `list_nodes(module_path, kind)` | Enumerate all nodes in a module filtered by kind | JSON: array of matching nodes |
| `find_node(name, kind)` | Search by (partial) name when you don't have the stable ID | JSON: matching node candidates |
| `find_definition_at(file, line)` | Reverse-lookup the node spanning a `file:line` location | Markdown: same shape as `explain()` |
| `callers(node_id, rel, paths)` | Fan-in lookup — *who calls this function?* | JSON: all caller nodes, resolved through stubs |
| `explain(node_id)` | Natural language understanding — *what does this do?* | Markdown: role, callers, callees, JSDoc |
| `centrality(top, kinds, group_by)` | SIR PageRank — rank nodes or modules by structural importance | Markdown: ranking table |
| `bridge_centrality(top, include_imports)` | Hub modules by connectivity — orchestrators and entry points | Markdown: ranking table |
| `framework_nodes(top)` | Framework-like hubs: high SIR + high connectivity | Markdown: ranking table |
| `analyze_repo()` | Structural health check — counts, coverage, distribution | Markdown: analysis report |
| `snapshot_list(limit, branch)` | Temporal tracking — *how has the codebase grown?* | JSON: snapshots with deltas, newest first |
| `snapshot_show(key)` | Snapshot detail — full metrics at a specific snapshot or `"latest"` | JSON: full metrics + hotspots + deltas |
| `snapshot_diff(key_a, key_b)` | Before/after comparison — *what changed between two snapshots?* | JSON: metrics for both + computed delta |

### CodeRank Tools

| Tool | Best for | Returns |
|---|---|---|
| `rank_nodes(top, rels, persist_metric, exclude_tests)` | Global weighted PageRank — most structurally important nodes | JSON: ranked nodes with scores |
| `query_ranked(q, k, mode, top, rels, radius, exclude_tests)` | Structure-aware query blending semantic + centrality + proximity | JSON: nodes with score components |
| `explain_rank(node_id, q)` | Why did this node rank here? — inbound counts, global rank, query scores | Markdown: rank explanation |

---

## 1. Orient First with `stats`

Always start here when approaching an unfamiliar codebase or after a rebuild.

```python
stats()
```

Returns counts broken down by node kind and edge relation, plus JSDoc coverage, in the
fleet's stats shape. For a typical TypeScript repo you'll see something like:

```json
{
  "kind": "code",
  "nodes": {
    "total": 1240,
    "by_kind": { "class": 27, "interface": 64, "type_alias": 41, "enum": 9, "function": 380, "method": 132, "module": 88, "symbol": 499 }
  },
  "edges": {
    "total": 2380,
    "by_rel": { "CALLS": 1310, "CONTAINS": 653, "IMPORTS": 310, "INHERITS": 18, "IMPLEMENTS": 52, "EXTENDS": 37 }
  },
  "meaningful_nodes": 741,
  "docstring_coverage": 0.58
}
```

High `symbol` counts mean many external package imports were recorded as `sym:` stubs. High `CALLS` counts mean the call graph is rich.

---

## 2. Semantic Exploration with `query`

Returns a ranked set of nodes and the edges between them. Good for mapping unknown territory.

### Find classes and their methods

```python
query("knowledge graph storage persistence")
```

Returns the relevant classes and the edges connecting them — no need to know filenames.

### Trace a call chain

```python
query("request pipeline middleware chain", rels=["CALLS"])
```

`rels=` restricts graph expansion to a single edge type. Set it to `["CALLS"]` to follow execution flow only.

### Explore the module import graph

```python
query("module imports dependencies", rels=["IMPORTS"])
```

### Find inheritance hierarchies

```python
query("base controller abstract class", rels=["INHERITS"])
```

### Find interface implementations

```python
query("storage adapter interface", rels=["IMPLEMENTS"])
```

`IMPLEMENTS` edges connect classes to the TypeScript interfaces they implement; `EXTENDS` edges connect interfaces to the interfaces they extend.

### Combine edge types

```python
query("build index embedding", rels=["CALLS", "IMPORTS"])
```

Listing several `rels` expands through multiple relation types simultaneously.

### Increase graph depth

```python
query("error handling exception", hop=2)
```

`hop=2` follows edges two levels out from each seed. Useful when the entry point is one hop away from the interesting logic.

### Filter weak semantic seeds

```python
query("error handling exception", min_score=0.25)
```

`min_score` filters low-similarity seeds before structural expansion.

### Keep module diversity

```python
query("storage layer", max_per_module=2)
```

`max_per_module` (default 3) caps returned nodes per module so one file does not dominate results. Pass `0` to disable.

---

## 3. Source Retrieval with `pack`

Returns Markdown with actual source snippets, ranked and deduplicated. Use this when you need to *read* the code, not just locate it.

### Understand an implementation

```python
pack("tree-sitter AST extraction visitor")
```

Returns the relevant declarations with surrounding source lines.

### Get context for a specific concept

```python
pack("graph expansion hop traversal", max_nodes=5)
```

`max_nodes` limits the number of snippets returned — useful when you only need the top results.

### Widen the snippet window

```python
pack("schema SQL CREATE TABLE", context=15)
```

`context=` controls how many lines of context appear above and below each definition. Default is 5; raise it for dense logic.

### Cap snippet length

```python
pack("markdown rendering output", max_lines=40)
```

`max_lines=` prevents very long functions from dominating the output.

### Increase semantic seeds

```python
pack("embedding model sqlite-vec index build", k=12)
```

`k=` is the number of semantic seed nodes before graph expansion. Raise it when the first results feel off-target.

### Tighten snippet packs

```python
pack("query expansion ranking", min_score=0.2, max_per_module=1)
```

Use `min_score` and `max_per_module` together to reduce noisy packs and improve cross-module coverage.

---

## 4. Pinpoint Lookup with `get_node`

Fetch a single node by its stable ID. Node IDs appear in `query` and `pack` results.
Follow with `neighbors(node_id)` for its edges.

### Node ID format

```
<kind>:<module_path>:<qualname>

fn:src/utils/helpers.ts:formatDate
meth:src/auth/middleware.ts:AuthMiddleware.verify
cls:src/auth/middleware.ts:AuthMiddleware
iface:src/types/storage.ts:StorageAdapter
type:src/types/config.ts:AppConfig
enum:src/types/errors.ts:ErrorCode
ns:src/legacy/api.ts:LegacyApi
mod:src/kg.ts
```

### Fetch a function

```python
get_node("fn:src/utils/helpers.ts:formatDate")
```

Returns module path, line range, node ID, and JSDoc.

### Fetch its immediate neighborhood

```python
neighbors("fn:src/utils/helpers.ts:formatDate")
neighbors("fn:src/utils/helpers.ts:formatDate", rels=["CALLS"], direction="out")
```

Returns the node's edges (CALLS, CONTAINS, IMPORTS, INHERITS, IMPLEMENTS, EXTENDS) and the nodes at
their far ends; `direction` is `"out"`, `"in"` or `"both"` (default). Use `callers()` when you need
callers resolved through `sym:` import stubs.

### Fetch a method

```python
get_node("meth:src/auth/middleware.ts:AuthMiddleware.verify")
```

### Fetch an interface

```python
get_node("iface:src/types/storage.ts:StorageAdapter")
```

### Fetch a module

```python
get_node("mod:src/index.ts")
```

---

## 5. Fan-In Lookup with `callers`

Find all nodes that call a given function, including cross-module callers resolved through `sym:` import stubs.

### Find direct and indirect callers

```python
callers("fn:src/utils/helpers.ts:formatDate")
```

Returns all functions that call `formatDate()`, with full node metadata (location, JSDoc, etc.).

### Restrict by relation type

```python
callers("cls:src/http/base.ts:BaseController", rel="INHERITS")     # all subclasses
callers("iface:src/types/storage.ts:StorageAdapter", rel="IMPLEMENTS")  # all implementations
callers("mod:src/config.ts", rel="IMPORTS")                        # all importers
```

The `rel` parameter (default `"CALLS"`) inverts any edge relation.

### Exclude test callers

```python
callers("fn:src/utils/helpers.ts:formatDate", paths="src/")
```

`paths=` filters callers to the given comma-separated module path prefixes — e.g. `"src/"` to see production callers only.

---

## 6. Natural-Language Explanation with `explain`

Get a structured understanding of what a code node does, who calls it, and what it calls.

### Explain a function

```python
explain("fn:src/utils/helpers.ts:formatDate")
```

Returns:
- **Role** — Kind, module, source location
- **Documentation** — Full JSDoc
- **Called By** — List of callers (top 10, with module paths)
- **Calls** — List of callees (what this function calls)

### Explain a method

```python
explain("meth:src/auth/middleware.ts:AuthMiddleware.verify")
```

### Explain a class

```python
explain("cls:src/auth/middleware.ts:AuthMiddleware")
```

Returns class-level metadata including methods and key callers.

---

## 7. Structural Importance with Centrality & CodeRank

### `centrality` — SIR PageRank

Rank nodes or modules by structural importance (weighted PageRank over the call graph).

```python
centrality(top=20)                      # top 20 nodes by importance
centrality(top=10, group_by="module")   # roll up by module
centrality(top=10, kinds="class,interface")  # filter to classes and interfaces
```

### `bridge_centrality` — hub module connectivity

Find modules that act as orchestrators or bridges — high connectivity across the graph.

```python
bridge_centrality(top=10)
bridge_centrality(top=10, include_imports=True)  # include import edges
```

### `framework_nodes` — most critical hubs

Composite score: `0.6×SIR + 0.4×connectivity`. Identifies the most load-bearing modules.

```python
framework_nodes(top=10)
```

### CodeRank tools — structure-aware search

| Tool | Purpose |
|---|---|
| `rank_nodes(top=25)` | Global weighted PageRank over the full repo |
| `query_ranked(q, mode="hybrid")` | 0.60×semantic + 0.25×centrality + 0.15×proximity |
| `query_ranked(q, mode="ppr")` | 0.70×personalized PageRank + 0.30×semantic |
| `explain_rank(node_id, q)` | Why did this node rank where it did? |

```python
# Find most important nodes globally
rank_nodes(top=25)

# Save scores for later use at query time
rank_nodes(persist_metric='coderank_global')

# Structure-aware search
query_ranked("database connection", mode="hybrid")
query_ranked("query pipeline", mode="ppr")

# Explain ranking
explain_rank("fn:src/utils/helpers.ts:formatDate")
explain_rank("fn:src/utils/helpers.ts:formatDate", q="date formatting")
```

**Typical structural importance workflow:**

```python
# Before refactoring: identify hotspots
centrality(top=20)                    → SIR ranking
bridge_centrality(top=10)             → hub modules
framework_nodes(top=10)               → most critical modules

# Impact-aware query
rank_nodes(top=25)                    → global PageRank
query_ranked("auth", mode="hybrid")   → structure-aware result
```

---

## 8. Temporal Tracking with Snapshot Tools

Track how the codebase evolves across commits — node/edge growth, coverage trends, complexity changes.

### List all snapshots

```python
snapshot_list()
```

Returns the 10 most recent snapshots (newest first), each with its key (a
release tag, or a UTC timestamp for an untagged capture), branch, timestamp,
version, key metrics, deltas vs. the previous snapshot, and freshness vs. the
live graph.

```python
snapshot_list(limit=0)              # return all snapshots
snapshot_list(branch="main")        # filter to a specific branch
```

### Show a specific snapshot

```python
snapshot_show()                    # most recent (default: "latest")
snapshot_show("0.4.0")             # specific key: the release tag it was saved under
```

Returns full metrics (nodes, edges, JSDoc coverage, critical issues, complexity median),
top hotspots, and deltas vs. both the previous and baseline snapshots.

### Compare two snapshots

```python
snapshot_diff("0.3.0", "0.4.0")        # keys from snapshot_list()
```

Returns metrics for both snapshots and a computed delta (b − a) covering: total nodes, total edges,
per-kind node count deltas, and per-relation edge count deltas.

### Typical snapshot workflow

```python
# 1. Discover available snapshot keys
snapshot_list()

# 2. Compare before/after a refactor
snapshot_diff("abc1234", "def5678")

# 3. Check the current state
snapshot_show("latest")
```

> Snapshots are captured automatically by the pre-commit hook (`tscodekg install-hooks`).
> They are stored in `.tscodekg/snapshots/` and are tracked in git — staged atomically with each commit.

---

## 9. Edge Type Reference

| Edge | Direction | Meaning | Source |
|---|---|---|---|
| `CONTAINS` | module → class/interface/function/… | Lexical containment | tree-sitter AST structure |
| `CALLS` | fn/method → fn | Direct function call | tree-sitter call expression |
| `IMPORTS` | module → module | `import` statement | tree-sitter import declaration |
| `INHERITS` | class → class | `class Foo extends Bar` | heritage clause |
| `IMPLEMENTS` | class → interface | `class Foo implements Bar` | heritage clause |
| `EXTENDS` | interface → interface | `interface Foo extends Bar` | extends clause |

Cross-module references to external packages are recorded as `sym:` stub targets; the centrality and CodeRank layers rewrite `sym:` targets through `RESOLVES_TO` edges when resolutions are available.

---

## 10. Parameter Quick Reference

### `query` and `pack` shared params

| Parameter | Default | Effect |
|---|---|---|
| `q` | *(required)* | Natural-language query |
| `k` | `8` | Semantic seed nodes before expansion |
| `hop` | `1` | Graph expansion hops from each seed |
| `rels` | all six | Edge types to traverse, as a list (`["CALLS", "IMPORTS"]`); omit for CONTAINS, CALLS, IMPORTS, INHERITS, IMPLEMENTS, EXTENDS |
| `max_nodes` | `25` / `15` | Cap returned nodes |
| `min_score` | `0.0` | Minimum semantic seed score |
| `max_per_module` | `3` | Cap per-module results (`0` disables) |
| `rerank_mode` | `"hybrid"` | `hybrid` / `semantic` / `legacy` |

### `pack` only

| Parameter | Default | Effect |
|---|---|---|
| `context` | `5` | Lines above/below each definition |
| `max_lines` | `60` | Max lines per snippet block |

---

## 11. Common Query Patterns

### "How does X work?"

```python
pack("X concept or class name")
```

### "What calls Y?"

```python
find_node("Y")                       # get the node ID
callers("fn:src/path.ts:Y")          # precise fan-in
```

### "What does module Z import?"

```python
query("module Z name", rels=["IMPORTS"])
```

### "Find all subclasses of Base"

```python
callers("cls:src/path.ts:Base", rel="INHERITS")
```

### "Find all implementations of an interface"

```python
callers("iface:src/types/path.ts:MyInterface", rel="IMPLEMENTS")
```

### "Show me the full structure of this module"

```python
query("module name", rels=["CONTAINS"], hop=2)
```

### "Get me the source for function F"

```python
# Step 1: find the node ID
find_node("F")
# Step 2: fetch it directly
get_node("fn:src/module/path.ts:F")
```

---

## 12. Excluding Directories from Indexing

By default, TypeScriptKG indexes all TS/JS files under the repo root. Excluding directories keeps metrics clean and queries accurate.

**Why exclude `__tests__/`?** Test directories pollute architectural analysis in three ways:
- Test entry points have no callers → they show up as **orphaned code**
- Test helpers become the top **fan-in** functions, hiding real hotspots
- Undocumented test functions drag **JSDoc coverage** well below production reality

**Configuration (`pyproject.toml`, persistent):**

```toml
[tool.tscodekg]
include = ["src"]           # top-level dirs to index (empty = all)
exclude = ["__tests__"]     # extra dirs to skip
```

Rebuild after changing the configuration: `tscodekg build --repo .`.

---

*Full rebuild: `tscodekg build --repo .` — `build` always wipes. Use `tscodekg update --repo .` for an incremental upsert.*
