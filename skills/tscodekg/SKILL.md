---
name: tscodekg
description: Expert knowledge for installing, configuring, and using the TypeScriptKG MCP server — a hybrid semantic + structural knowledge graph for TypeScript/JavaScript codebases. Use this skill when the user asks about: setting up TypeScriptKG in a project, installing tscode-kg with pip or Poetry (pip install tscode-kg), building the SQLite graph or sqlite-vec vector index, configuring .mcp.json for Claude Code or Kilo Code, configuring .vscode/mcp.json for GitHub Copilot, configuring claude_desktop_config.json for Claude Desktop, using the tscodekg CLI (tscodekg init, tscodekg build, tscodekg query, tscodekg pack, tscodekg analyze, tscodekg centrality, tscodekg bridges, tscodekg framework-nodes, tscodekg explain, tscodekg snapshot, tscodekg install-hooks, tscodekg download-model, tscodekg mcp), using the graph_stats / query_codebase / pack_snippets / callers / get_node / list_nodes / find_node / centrality / bridge_centrality / framework_nodes / find_definition_at / analyze_repo / explain / rank_nodes / query_ranked / explain_rank / snapshot_list / snapshot_show / snapshot_diff MCP tools, or troubleshooting TypeScriptKG errors.
---

# TypeScriptKG Skill

> **Use TypeScriptKG first — before grep, Glob, or file reads.**
>
> Grep and file search find text. TypeScriptKG understands code. It knows what calls what, what implements which interface, which modules are imported where, and surfaces the most semantically relevant source snippets in a single query. One `pack_snippets` call replaces five rounds of grep-and-read and gives the agent real structural insight into the codebase — not just line matches.

TypeScriptKG (package `tscode-kg`, import `tscode_kg`) indexes TypeScript/JavaScript repos into a hybrid knowledge graph (SQLite + sqlite-vec) via tree-sitter AST extraction on the shared kgmodule-utils SDK, and exposes it as MCP tools for AI agents.

## Installation

```bash
# pip — full KG stack (graph store + sqlite-vec index + hybrid query + MCP server)
pip install tscode-kg

# Poetry
poetry add tscode-kg

# From source
poetry add "tscode-kg @ git+https://github.com/Flux-Frontiers/tscode_kg.git"
```

The base package carries the whole stack — `kgmodule-utils[semantic,sqlite-vec]`, `mcp`, and `networkx` — so build/query/analyze/MCP all work from a plain install. Optional extras cover cross-KG (`kgdeps`) and the visualizers (`viz`, `viz3d`).

## One-Command Setup

```bash
# Downloads the embedding model, builds graph + index, installs the
# pre-commit hook, and captures an initial snapshot
tscodekg init --repo .
```

Flags: `--model` (embedding model), `--skip-hooks`, `--skip-snapshot`, `--force`.

## Build the Knowledge Graph

TypeScriptKG has a **single build command** — there is no `build-sqlite` / `build-index` split:

```bash
# Graph + vector index in one step
tscodekg build --repo .

# Graph only (skip embeddings)
tscodekg build --repo . --graph-only

# Vector index only (graph must already exist)
tscodekg build --repo . --index-only

# Rebuild from scratch
tscodekg build --repo .
```

Artifacts (all under `.tscodekg/`):

| Artifact | Path |
|---|---|
| SQLite graph | `.tscodekg/graph.sqlite` |
| sqlite-vec vector store | `.tscodekg/vectors.sqlite` |
| Temporal snapshots | `.tscodekg/snapshots/` |

Override with `--db` and `--vectors` if needed — defaults resolve relative to `--repo`.

## Rebuilding After Code Changes

The knowledge graph is a snapshot of the codebase at build time. It does **not** update automatically. Stale data causes misleading query results — especially after renames, deletions, or large refactors.

```bash
# Full rebuild (recommended after any structural change)
tscodekg build --repo .
```

> **Why `build` always wipes:** deleted or renamed nodes would otherwise remain as phantom entries. The vector store upserts by node ID, so a renamed symbol keeps its old entry forever. `build` clears both stores unconditionally; use `update` only when you are sure nothing was deleted or renamed. Same split as `pycodekg`.

## CLI Commands

Each command is available as `tscodekg <subcommand>` **or** a dedicated `tscodekg-<name>` script — both forms are equivalent:

| Subcommand / Script alias | Purpose |
|---|---|
| `init` / `tscodekg-init` | One-command setup: model, build, hooks, snapshot |
| `build` / `tscodekg-build` | Full rebuild — wipes, then SQLite graph + sqlite-vec index (`--graph-only`, `--index-only`) |
| `update` / `tscodekg-update` | Incremental upsert; same options as `build`, no wipe |
| `query` / `tscodekg-query` | Hybrid semantic + structural query (`-k`, `--hop`, `--max-nodes`, `--rerank` hybrid/semantic/legacy) |
| `pack` / `tscodekg-pack` | Source-grounded snippet packs (`--max-lines`, `--out` file.md/.json) |
| `analyze` / `tscodekg-analyze` | Thorough 14-phase architectural analysis (`-o report.md`, `--write-centrality`) |
| `centrality` / `tscodekg-centrality` | SIR PageRank — rank nodes or modules by structural importance |
| `bridges` | Module connectivity ranking — orchestrator/hub modules |
| `framework-nodes` | Framework-like hubs: high SIR + high connectivity |
| `explain` | Natural-language explanation of a node by ID |
| `viz` / `tscodekg-viz` | Streamlit interactive graph explorer (`--port`, `--no-browser`; needs `[viz]` extra) |
| `viz3d` / `tscodekg-viz3d` | 3-D PyVista visualizer (`--layout` allium/funnel; needs `[viz3d]` extra) |
| `viz-timeline` / `tscodekg-viz-timeline` | Plotly timeline of snapshot metrics (`--type` 2d/3d; needs `[viz]` extra) |
| `snapshot save [VERSION]` | Capture a metrics snapshot (branch/tree-hash auto-detected) |
| `snapshot list` | List snapshots newest-first (`--json`) |
| `snapshot show <key>` | Full details for one snapshot |
| `snapshot diff <a> <b>` | Compare two snapshots side-by-side |
| `snapshot prune` | Remove stale snapshots (`--dry-run`) |
| `install-hooks` / `tscodekg-install-hooks` | Install pre-commit git hook for automatic snapshots |
| `download-model` / `tscodekg-download-model` | Pre-download embedding model for offline use |
| `mcp` / `tscodekg-mcp` | Start MCP server (`--repo`, `--db`, `--vectors`, `--transport` stdio/sse) |

For detailed options: `tscodekg <command> --help`.

## Directory Includes / Excludes

Configure via `[tool.tscodekg]` in `pyproject.toml`:

```toml
[tool.tscodekg]
include = ["src"]        # top-level dirs to index (unset = all)
exclude = ["tests"]      # extra dir names excluded at every depth
```

Excluding `tests/` keeps fan-in metrics, orphan detection, and JSDoc coverage grounded in production code.

## Snapshots & Pre-Commit Hook

```bash
tscodekg install-hooks --repo .        # install the pre-commit snapshot hook (--force to overwrite)
TSCODEKG_SKIP_SNAPSHOT=1 git commit    # skip the hook for one commit
```

Snapshots live in `.tscodekg/snapshots/` and power the `snapshot_*` MCP tools.

## Offline Setup

```bash
# Pre-download the embedding model (CI, air-gapped nets, HF rate limits)
tscodekg download-model
```

Subsequent builds and queries use the cached local copy without network access.

## Configure Claude Code / Kilo Code (.mcp.json)

Both read per-repo config from `.mcp.json` in the project root:

```json
{
  "mcpServers": {
    "tscodekg": {
      "command": "tscodekg",
      "args": [
        "mcp",
        "--repo", "/absolute/path/to/repo",
        "--db",   "/absolute/path/to/repo/.tscodekg/graph.sqlite"
      ]
    }
  }
}
```

Always use **absolute paths**. Merge into existing `mcpServers` — don't overwrite other entries.

> ⚠️ Do NOT add `tscodekg` to any global settings file — use per-repo `.mcp.json` only.

## Configure GitHub Copilot (.vscode/mcp.json)

GitHub Copilot uses a different schema — `"servers"` key and `"type": "stdio"` required:

```json
{
  "servers": {
    "tscodekg": {
      "type": "stdio",
      "command": "tscodekg",
      "args": [
        "mcp",
        "--repo", "/absolute/path/to/repo",
        "--db",   "/absolute/path/to/repo/.tscodekg/graph.sqlite"
      ]
    }
  }
}
```

VS Code will prompt you to **Trust** the server on first use.

## Configure Claude Desktop (claude_desktop_config.json)

Claude Desktop has no Poetry/venv on PATH — use the absolute binary:

```bash
poetry env info --path
# → /path/to/venv ; binary: /path/to/venv/bin/tscodekg
```

Config path: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)

```json
{
  "mcpServers": {
    "tscodekg": {
      "command": "/path/to/venv/bin/tscodekg",
      "args": ["mcp", "--repo", "/abs/path", "--db", "/abs/path/.tscodekg/graph.sqlite"]
    }
  }
}
```

## MCP Tools

| Tool | When to use |
|---|---|
| `graph_stats()` | First call — understand codebase size/shape |
| `query_codebase(q, k, hop, rels, max_nodes, min_score, max_per_module, rerank_mode)` | Explore graph structure, find relevant nodes; tune precision with `min_score`, diversity with `max_per_module` |
| `pack_snippets(q, k, hop, rels, context, max_lines, ...)` | Read actual source code (prefer over query_codebase) |
| `get_node(node_id, include_edges)` | Fetch node metadata; `include_edges=True` also returns outgoing edges + incoming callers |
| `list_nodes(module_path, kind)` | List nodes filtered by module path prefix and/or kind |
| `find_node(name, kind)` | Find nodes by plain name or qualname substring |
| `find_definition_at(path, line)` | Resolve the definition enclosing a file:line position — IDE-style "go to definition" |
| `callers(node_id, rel, paths)` | Fan-in lookup, resolving cross-module `sym:` stubs with import-aware filtering for ambiguous names |
| `explain(node_id)` | Natural-language explanation of a node: role, JSDoc, callers, callees |
| `centrality(top, kinds, group_by)` | SIR PageRank — rank nodes or modules by structural importance; use before refactoring |
| `bridge_centrality(top, include_imports)` | Module connectivity ranking — orchestrator/hub modules |
| `framework_nodes(top)` | Framework-like hub modules: high SIR + high connectivity |
| `analyze_repo()` | Full architectural analysis — coupling, coverage, orphans, quality grade |
| `snapshot_list(limit, branch)` | List saved metric snapshots newest-first |
| `snapshot_show(key)` | Full metrics for a snapshot key (tree hash) or `"latest"`, with freshness check vs. the live graph |
| `snapshot_diff(key_a, key_b)` | Compare two snapshots — node/edge/coverage/issues delta |

## CodeRank Tools

Structure-aware ranking that blends PageRank with semantic search.

| Tool | When to use |
|---|---|
| `rank_nodes(top, rels, persist_metric, exclude_tests)` | Global weighted CodeRank (PageRank) — most structurally important nodes across the repo |
| `query_ranked(q, k, mode, top, rels, radius, exclude_tests)` | CodeRank-enhanced query: `hybrid` (semantic + centrality + proximity) or `ppr` (personalized PageRank + semantic) |
| `explain_rank(node_id, q)` | Explain why a node ranked where it did — inbound counts, global rank, query-conditioned scores |

**CodeRank workflows:**
- Find most important nodes globally: `rank_nodes(top=25)` → `explain_rank`
- Persist global rank for later queries: `rank_nodes(persist_metric='coderank_global')`
- Structure-aware query: `query_ranked(q='request middleware', mode='hybrid')`

## Query Strategy Guide

### Choosing `k` and `hop`

| Goal | Settings |
|---|---|
| Narrow, precise lookup | `k=4, hop=0` |
| Standard exploration | `k=8, hop=1` (default) |
| Broad context sweep | `k=12, hop=2` |
| Deep dependency trace | `k=8, hop=2, rels="CALLS,IMPORTS"` |

### Choosing `rels`

| Relation | When to include |
|---|---|
| `CONTAINS` | Almost always — structural context |
| `CALLS` | Tracing execution flow |
| `IMPORTS` | Dependency analysis (module → module) |
| `INHERITS` | Class hierarchy (`class extends class`) |
| `IMPLEMENTS` | Class → interface conformance |
| `EXTENDS` | Interface → interface hierarchy |
| `RESOLVES_TO` | Connecting `sym:` stubs to definitions — used internally by `callers()`; include for traversal through import aliases |

### Typical session workflow

```
1. graph_stats()                                              → orientation
2. query_codebase("auth middleware", k=8, hop=1)              → find nodes
3. explain("cls:src/auth/middleware.ts:AuthMiddleware")       → understand before reading
4. pack_snippets("JWT validation", k=6, hop=1)                → read source
5. get_node("fn:src/utils/helpers.ts:formatDate", include_edges=True)
                                                              → node detail + neighborhood in one call
6. pack_snippets("error handling", k=4, hop=2, rels="CALLS")  → deeper
7. snapshot_list() / snapshot_diff("a", "b")                  → track codebase evolution
```

### Structural importance workflows

```
centrality(top=20)                                → SIR ranking by node
centrality(top=10, group_by="module")             → SIR ranking by module
bridge_centrality(top=10)                         → hub modules by connectivity
framework_nodes(top=10)                           → most critical hub modules

rank_nodes(top=25)                                → global PageRank ranking
query_ranked("request routing", mode="hybrid")    → structure-aware query
explain_rank("fn:src/router/index.ts:route")      → why did this rank here?
```

## .gitignore Setup

The `.tscodekg/` directory holds the SQLite graph, sqlite-vec store, and snapshots. Graph and index are reproducible artifacts:

```gitignore
.tscodekg/
```

If you want snapshot history in git, un-ignore `.tscodekg/snapshots/` — the pre-commit hook stages snapshots atomically with each commit.

## Key Defaults

- `k=8, hop=1`; default rels: `CONTAINS,CALLS,IMPORTS,INHERITS` (add `IMPLEMENTS,EXTENDS` for TS type structure)
- Node kinds: `module`, `class`, `interface`, `type_alias`, `enum`, `namespace`, `function`, `method`
- Node ID format: `<prefix>:<module_path>:<qualname>` — e.g. `cls:src/auth/middleware.ts:AuthMiddleware`, `fn:src/utils/helpers.ts:formatDate`
- Prefixes: `mod:` module, `cls:` class, `iface:` interface, `type:` type alias, `enum:` enum, `ns:` namespace, `fn:` function, `meth:` method, `sym:` unresolved external symbol
- Transport: `stdio` (Claude Code/Desktop), `sse` (HTTP clients)

## Troubleshooting

| Error | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'mcp'` | Install the extra: `pip install tscode-kg` |
| `WARNING: SQLite database not found` | Run `tscodekg build --repo .` first |
| MCP server not appearing | Use absolute paths in `.mcp.json`; restart Claude Code |
| Empty query results | Rebuild the index: `tscodekg build --repo . --index-only` |
| Pre-commit hook slow / unwanted for one commit | `TSCODEKG_SKIP_SNAPSHOT=1 git commit ...` |
| Wrong files indexed | Set `[tool.tscodekg] include` / `exclude` in `pyproject.toml`, then `tscodekg build` (not `update`) |

## Full Reference

See `references/installation.md` for complete CLI flags, MCP config templates, gitignore recommendations, and the troubleshooting table. See `references/CHEATSHEET.md` for a query cookbook covering all MCP tools.
