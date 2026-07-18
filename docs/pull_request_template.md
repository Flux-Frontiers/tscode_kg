# PR: Add Structural Importance Ranking (SIR) centrality analysis

## Summary

This PR adds **Structural Importance Ranking (SIR)** to TypeScriptKG: a deterministic weighted-PageRank analysis over the resolved structural graph.

## Why

TypeScriptKG already builds a deterministic SQLite-backed knowledge graph from tree-sitter AST structure and adds `RESOLVES_TO` edges to recover cross-module call relationships. SIR extends that model with an explainable notion of architectural importance: components rank highly when many important parts of the system rely on them.

## Included

- `docs/CODERANK.md`
- `src/tscode_kg/centrality.py`
- `src/tscode_kg/cli/cmd_centrality.py`
- `tests/test_centrality.py`

## Features

- weighted PageRank over `CALLS`, `INHERITS`, `IMPLEMENTS`, `EXTENDS`, `IMPORTS`, `CONTAINS`
- `sym:` stub normalization through existing `RESOLVES_TO` edges
- cross-module dependency boosting
- optional private-symbol penalty
- node-level and module-level rankings
- optional persistence to `centrality_scores`

## Example

```bash
tscodekg centrality --db .tscodekg/graph.sqlite --top 25
tscodekg centrality --db .tscodekg/graph.sqlite --group-by module
tscodekg centrality --db .tscodekg/graph.sqlite --write-db
```

## Notes

The repo uses a Click-based CLI under `src/tscode_kg/cli/` and keeps SQLite schema creation inline in the shared `kgmodule-utils` store, so this PR follows that architecture rather than introducing a new migration framework.
