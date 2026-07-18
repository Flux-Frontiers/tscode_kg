# TypeScriptKG

Knowledge graph for TypeScript and JavaScript codebases — deterministic AST extraction, hybrid semantic + structural search.

## Overview

TypeScriptKG builds a queryable knowledge graph from TypeScript/JavaScript source code using:

- **tree-sitter** for deterministic, parser-level AST extraction (no LLM inference during indexing)
- **SQLite** for the structural graph (nodes, edges, provenance)
- **sqlite-vec** for the semantic vector index (embeddings via `BAAI/bge-small-en-v1.5`)
- **Hybrid retrieval**: semantic seed → graph hop expansion → lexical re-ranking

## Node types

| Kind | Description |
|------|-------------|
| `module` | Every indexed `.ts`/`.tsx`/`.js`/`.jsx` file |
| `class` | Class declaration |
| `interface` | TypeScript interface |
| `type_alias` | TypeScript type alias |
| `enum` | TypeScript enum |
| `namespace` | TypeScript namespace / module declaration |
| `function` | Module-level function (declaration or `const` arrow) |
| `method` | Method or accessor within a class |
| `symbol` | Unresolved external import stub |

## Edge types

| Relation | Description |
|----------|-------------|
| `CONTAINS` | module → class/function/interface… |
| `IMPORTS` | module → module |
| `CALLS` | function/method → function |
| `INHERITS` | class extends class |
| `IMPLEMENTS` | class implements interface |
| `EXTENDS` | interface extends interface |

## Quick start

```bash
pip install tscode-kg

# First-time setup (downloads model, builds graph, installs hooks, snapshots)
tscodekg init --repo /path/to/ts-repo

# Build the KG for a TypeScript repo
tscodekg build --repo /path/to/ts-repo

# Query
tscodekg query "authentication middleware"
tscodekg pack "error handling utilities" --hop 2

# Thorough architectural analysis (fan-in/out, CodeRank, SIR centrality, JSDoc coverage)
tscodekg analyze /path/to/ts-repo --report analysis.md

# Structural rankings and node explanations
tscodekg centrality --top 20
tscodekg bridges --top 20
tscodekg framework-nodes --top 20
tscodekg explain "fn:src/utils/helpers.ts:formatDate"

# Temporal metric snapshots
tscodekg snapshot save --repo /path/to/ts-repo
tscodekg snapshot list

# Install the pre-commit snapshot hook
tscodekg install-hooks --repo /path/to/ts-repo

# MCP server (Claude Desktop, Cursor, etc.)
tscodekg mcp --repo /path/to/ts-repo
```

Each subcommand is also available as a dedicated script alias — `tscodekg-init`,
`tscodekg-build`, `tscodekg-query`, `tscodekg-pack`, `tscodekg-analyze`,
`tscodekg-centrality`, `tscodekg-install-hooks`, `tscodekg-download-model`,
`tscodekg-mcp` — both forms are equivalent.

## MCP tools

The MCP server exposes the full PyCodeKG toolkit, applied to TypeScript/JavaScript
codebases: `graph_stats`, `query_codebase`, `pack_snippets`, `callers`, `get_node`,
`list_nodes`, `find_node`, `centrality`, `bridge_centrality`, `framework_nodes`,
`find_definition_at`, `analyze_repo`, `explain`, `rank_nodes`, `query_ranked`,
`explain_rank`, `snapshot_list`, `snapshot_show`, and `snapshot_diff`.

See `docs/MCP.md` for setup and `docs/CHEATSHEET.md` for a query cookbook.
Repo-local Claude Code skills live in `skills/`.

## Snapshots & git hook

`tscodekg snapshot save` captures graph metrics (nodes, edges, JSDoc coverage,
issues, hotspots) keyed by git tree hash into `.tscodekg/snapshots/`, with
deltas computed against the previous and baseline snapshots.
`tscodekg install-hooks` installs a pre-commit hook that rebuilds the index,
captures a snapshot, stages the snapshot directory, and then runs the
pre-commit framework checks — so every commit records the state of the
knowledge graph. Skip it for one commit with `TSCODEKG_SKIP_SNAPSHOT=1`.

## Python API

```python
from tscode_kg import TypeScriptKG

kg = TypeScriptKG(repo_root="/path/to/ts-repo")
stats = kg.build(wipe=True)

result = kg.query("authentication middleware", k=8)
result.print_summary()

pack = kg.pack("error handling", k=8, hop=1)
pack.save("context.md")
```

## Architecture

TypeScriptKG is a domain implementation of the `KGModule` base class from `kgmodule-utils`.
Only the TypeScript/JS-specific extraction layer is implemented here — all generic
infrastructure (SQLite, sqlite-vec, hybrid query, snippet packing) is inherited from
`KGModule`.

## Configuration

In your project's `pyproject.toml`:

```toml
[tool.tscodekg]
include = ["src"]           # top-level dirs to index (empty = all)
exclude = ["__tests__"]     # extra dirs to skip
```

## Author

Eric G. Suchanek, PhD — Flux Frontiers

## License

Elastic-2.0
