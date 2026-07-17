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

# Build the KG for a TypeScript repo
tscodekg build --repo /path/to/ts-repo

# Query
tscodekg query "authentication middleware"
tscodekg pack "error handling utilities" --hop 2

# MCP server (Claude Desktop, Cursor, etc.)
tscodekg mcp --repo /path/to/ts-repo
```

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
