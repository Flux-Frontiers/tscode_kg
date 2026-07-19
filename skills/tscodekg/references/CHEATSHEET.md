# TypeScriptKG Query Cheatsheet

A practical reference for the TypeScriptKG MCP tools, with generic TypeScript/JavaScript examples. All queries run against the live `.tscodekg/graph.sqlite` + `.tscodekg/vectors.sqlite` index.

---

## The Tools at a Glance

### Core Tools

| Tool | Best for | Returns |
|---|---|---|
| `graph_stats()` | Orientation — size and shape of the graph | Markdown: node/edge counts by kind |
| `query_codebase(q, k, hop, rels, ...)` | Structural exploration — *what exists, how things relate* | JSON: ranked nodes + edges |
| `pack_snippets(q, k, hop, ...)` | Implementation detail — *actual source code* | Markdown: snippets with line numbers |
| `get_node(node_id, include_edges)` | Pinpoint lookup — one node by stable ID + optional neighborhood | Full node metadata |
| `list_nodes(module_path, kind)` | Enumerate nodes in a module filtered by kind | JSON: matching nodes |
| `find_node(name, kind)` | Locate a node when you only know its name | JSON: matching nodes |
| `find_definition_at(path, line)` | IDE-style "go to definition" for a file:line position | The enclosing definition node |
| `callers(node_id, rel)` | Fan-in lookup — *who calls this function?* | JSON: caller nodes, resolved through `sym:` stubs |
| `explain(node_id)` | Natural-language understanding — *what does this do?* | Markdown: role, callers, callees, JSDoc |
| `centrality(top, kinds, group_by)` | SIR PageRank — structural importance ranking | Markdown: ranking table |
| `bridge_centrality(top, include_imports)` | Hub modules by connectivity — orchestrators | Markdown: ranking table |
| `framework_nodes(top)` | Framework-like hubs: high SIR + high connectivity | Markdown: ranking table |
| `analyze_repo()` | Full architectural health check | Markdown: multi-phase analysis |
| `snapshot_list(limit, branch)` | Temporal tracking — *how has the codebase grown?* | JSON: snapshots, newest first |
| `snapshot_show(key)` | Full metrics at a snapshot key or `"latest"` | JSON: metrics + freshness check |
| `snapshot_diff(key_a, key_b)` | Before/after comparison between snapshots | JSON: computed delta |

### CodeRank Tools

| Tool | Best for | Returns |
|---|---|---|
| `rank_nodes(top, rels, persist_metric, exclude_tests)` | Global weighted PageRank — most important nodes | JSON: ranked nodes with scores |
| `query_ranked(q, k, mode, top, rels, radius, exclude_tests)` | Structure-aware query blending semantic + centrality + proximity | JSON: nodes with score components |
| `explain_rank(node_id, q)` | Why did this node rank here? | Markdown: rank explanation |

---

## 1. Orient First with `graph_stats`

Always start here when approaching an unfamiliar codebase or after a rebuild.

```python
graph_stats()
```

Returns counts broken down by node kind (`module`, `class`, `interface`, `type_alias`, `enum`, `namespace`, `function`, `method`) and edge relation (`CALLS`, `IMPORTS`, `CONTAINS`, `INHERITS`, `IMPLEMENTS`, `EXTENDS`, `RESOLVES_TO`). High `CALLS` counts mean a rich call graph; many `sym:` nodes mean lots of external / unresolved imports.

---

## 2. Semantic Exploration with `query_codebase`

Returns a ranked set of nodes and the edges between them. Good for mapping unknown territory.

```python
# Find classes and their methods — no filenames needed
query_codebase("authentication middleware session handling")

# Trace a call chain
query_codebase("request routing dispatch", rels="CALLS")

# Explore the module import graph
query_codebase("module imports dependencies", rels="IMPORTS")

# Find interface implementations
query_codebase("repository interface data access", rels="IMPLEMENTS")

# Follow interface hierarchies
query_codebase("base props component interface", rels="EXTENDS")

# Combine edge types
query_codebase("build pipeline bundler", rels="CALLS,IMPORTS")

# Increase graph depth
query_codebase("error handling exception", hop=2)

# Filter weak semantic seeds
query_codebase("error handling", min_score=0.25)

# Keep module diversity
query_codebase("state management", max_per_module=2)
```

---

## 3. Source Retrieval with `pack_snippets`

Returns Markdown with actual source snippets, ranked and deduplicated. Use this when you need to *read* the code, not just locate it.

```python
# Understand an implementation
pack_snippets("JWT token validation refresh")

# Limit result count
pack_snippets("graph traversal hop expansion", max_nodes=5)

# Widen the snippet window (lines of context around each definition)
pack_snippets("schema definition zod validation", context=15)

# Cap snippet length
pack_snippets("render component tree", max_lines=40)

# Raise semantic seeds when first results feel off-target
pack_snippets("websocket reconnect backoff", k=12)

# Tighten noisy packs
pack_snippets("query ranking", min_score=0.2, max_per_module=1)
```

---

## 4. Pinpoint Lookup with `get_node`, `find_node`, `find_definition_at`

### Node ID format

```
<prefix>:<module_path>:<qualname>

fn:src/utils/helpers.ts:formatDate
cls:src/auth/middleware.ts:AuthMiddleware
meth:src/auth/middleware.ts:AuthMiddleware.handle
iface:src/types/user.ts:UserProfile
type:src/types/api.ts:ApiResponse
enum:src/constants.ts:LogLevel
ns:src/legacy/global.d.ts:MyApp
mod:src/index.ts
```

```python
# Fetch a function (lineno, end_lineno, JSDoc, module_path, qualname)
get_node("fn:src/utils/helpers.ts:formatDate")

# Fetch with immediate neighborhood — outgoing edges + incoming callers in one call
get_node("cls:src/auth/middleware.ts:AuthMiddleware", include_edges=True)

# When you only know the name
find_node("AuthMiddleware")
find_node("format", kind="function")

# When you only know a file and line (e.g. from a stack trace)
find_definition_at("src/auth/middleware.ts", 42)
```

---

## 5. Fan-In Lookup with `callers`

Find all nodes that call a given function, including cross-module callers resolved through `sym:` stubs. When same-name definitions exist in multiple modules, import-aware filtering avoids false-positive fan-in links.

```python
callers("fn:src/store/graph.ts:expand")

# Other relation types — e.g. all subclasses / implementors
callers("cls:src/base/controller.ts:BaseController", rel="INHERITS")
callers("iface:src/types/repo.ts:Repository", rel="IMPLEMENTS")
```

---

## 6. Natural-Language Explanation with `explain`

```python
explain("fn:src/store/graph.ts:expand")
explain("meth:src/auth/middleware.ts:AuthMiddleware.handle")
explain("cls:src/auth/middleware.ts:AuthMiddleware")
```

Returns role (kind, module, location), documentation (JSDoc), callers, and callees.

---

## 7. Structural Importance with Centrality & CodeRank

```python
centrality(top=20)                      # top 20 nodes by SIR PageRank
centrality(top=10, group_by="module")   # roll up by module
centrality(top=10, kinds="class")       # filter to classes only

bridge_centrality(top=10)                       # hub modules by connectivity
bridge_centrality(top=10, include_imports=True) # include import edges

framework_nodes(top=10)                 # composite: high SIR + high connectivity
```

### CodeRank — structure-aware search

```python
rank_nodes(top=25)                                   # global weighted PageRank
rank_nodes(persist_metric='coderank_global')         # persist scores for query time
query_ranked("database connection", mode="hybrid")   # semantic + centrality + proximity
query_ranked("query pipeline", mode="ppr")           # personalized PageRank + semantic
explain_rank("fn:src/store/graph.ts:expand")         # why did this rank here?
explain_rank("fn:src/store/graph.ts:expand", q="database connection")
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

```python
snapshot_list()                     # 10 most recent, newest first
snapshot_list(limit=0)              # all snapshots
snapshot_list(branch="main")        # filter by branch

snapshot_show()                     # most recent (default "latest") + freshness vs. live graph
snapshot_show("abc1234")            # specific tree-hash key

snapshot_diff("abc1234", "def5678") # metrics for both + computed delta
```

> Snapshots are captured automatically by the pre-commit hook (`tscodekg install-hooks`) and stored in `.tscodekg/snapshots/`. Skip for one commit with `TSCODEKG_SKIP_SNAPSHOT=1 git commit ...`.

---

## 9. Edge Type Reference

| Edge | Direction | Meaning | Source |
|---|---|---|---|
| `CONTAINS` | module → class/function/interface…, class → method | Lexical containment | tree-sitter AST structure |
| `CALLS` | function/method → function | Direct call (best-effort via call expressions) | tree-sitter call expressions |
| `IMPORTS` | module → module | `import` statement (resolved from import paths) | import declarations |
| `INHERITS` | class → class | `class Foo extends Bar` | heritage clause |
| `IMPLEMENTS` | class → interface | `class Foo implements Bar` | heritage clause |
| `EXTENDS` | interface → interface | `interface Foo extends Bar` | heritage clause |
| `RESOLVES_TO` | symbol → node | `sym:` stub resolves to its definition | import/name binding |

---

## 10. Parameter Quick Reference

### `query_codebase` and `pack_snippets` shared params

| Parameter | Default | Effect |
|---|---|---|
| `q` | *(required)* | Natural-language query |
| `k` | `8` | Semantic seed nodes before expansion |
| `hop` | `1` | Graph expansion hops from each seed |
| `rels` | `"CONTAINS,CALLS,IMPORTS,INHERITS"` | Edge types to traverse (add `IMPLEMENTS,EXTENDS` for TS type structure) |
| `max_nodes` | `25` / `15` | Cap returned nodes |
| `min_score` | unset | Filter low-similarity seeds before expansion |
| `max_per_module` | unset | Cap nodes per module for diversity |
| `rerank_mode` | `hybrid` | `hybrid`, `semantic`, or `legacy` |

### `pack_snippets` only

| Parameter | Default | Effect |
|---|---|---|
| `context` | `5` | Lines above/below each definition |
| `max_lines` | `60` | Max lines per snippet block |

---

## 11. Common Query Patterns

```python
# "How does X work?"
pack_snippets("X concept or class name")

# "What calls Y?"
callers("fn:src/path/file.ts:Y")

# "What does module Z import?"
query_codebase("module Z name", rels="IMPORTS")

# "Find all subclasses of Base"
callers("cls:src/base.ts:Base", rel="INHERITS")

# "What implements this interface?"
callers("iface:src/types/repo.ts:Repository", rel="IMPLEMENTS")

# "Show me the full structure of this module"
query_codebase("module name", rels="CONTAINS", hop=2)

# "Get me the source for function F"
find_node("F", kind="function")     # step 1: find the node ID
get_node("fn:src/module/path.ts:F") # step 2: fetch it directly

# "What's defined at this stack-trace location?"
find_definition_at("src/api/client.ts", 128)
```

---

## 12. Excluding Directories from Indexing

By default, TypeScriptKG indexes directories per `[tool.tscodekg]` (all when unset). Excluding tests keeps metrics clean:

- Test entry points have no callers → they show up as **orphaned code**
- Test helpers become the top **fan-in** functions, hiding real hotspots
- Undocumented test functions drag **JSDoc coverage** below production reality

```toml
[tool.tscodekg]
include = ["src"]        # only index these top-level dirs
exclude = ["tests"]      # exclude at every depth
```

Rebuild after changing includes/excludes: `tscodekg build --repo . --wipe`
