# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **BREAKING: vector store migrated from LanceDB to sqlite-vec**, mirroring the
  PyCodeKG/DocKG refactor. `kgmodule-utils[semantic,sqlite-vec]>=0.6.2` and
  `TypeScriptKG.__init__` now passes `vector_backend="sqlite-vec"` to the
  `KGModule` base class. Vectors live in a single `.tscodekg/vectors.sqlite`
  file. **Migration: run `tscodekg build` once after upgrading.**
  - `TypeScriptKG(repo_root, db_path, vectors_path)` — `lancedb_dir` renamed
    to `vectors_path`.
  - CLI: `--lancedb` → `--vectors` on `build` and `mcp`.
  - MCP server: `--lancedb` → `--vectors`.
- **Migrated type checker from mypy → [ty](https://github.com/astral-sh/ty)**
  across `pyproject.toml` and `.pre-commit-config.yaml`
  (`poetry run ty check src/`). `[tool.mypy]` replaced with
  `[tool.ty.environment]` / `[tool.ty.rules]` (`unresolved-import = "ignore"`
  mirrors mypy's `ignore_missing_imports`).
- **Dependency layout reorganized to match what the code actually requires.**
  `kgmodule-utils` (bare, for the `NodeSpec`/`EdgeSpec`/`KGExtractor` types
  `extractor.py` is built on) and `click` (drives the `tscodekg` command
  group) moved from the `kg` extra to core `dependencies`; `kg` keeps
  `kgmodule-utils[semantic,sqlite-vec]`, `mcp`, and `networkx` for the
  full build/query/analyze/MCP path.
- Bumped `rich>=14.3.3,<15`, `tree-sitter>=0.25.0`,
  `tree-sitter-typescript>=0.23.2` to match current releases.

### Added

- **New `kgdeps` optional-dependency group** (`pycode-kg>=0.20.0`,
  `doc-kg>=0.18.1`) so PyCodeKG and DocKG are usable directly from within
  this repo.
- **`.pre-commit-config.yaml`** and `.secrets.baseline`, adapted from
  PyCodeKG's config (ruff check/format, detect-secrets, `ty`, pytest as
  local hooks); installed via `pre-commit install`.
- **`tscode_kg/centrality.py`** — Structural Importance Ranking (weighted
  PageRank over CALLS/INHERITS/IMPLEMENTS/EXTENDS/IMPORTS/CONTAINS edges),
  ported from PyCodeKG and adapted to the TS/JS node/edge vocabulary
  (`interface`, `IMPLEMENTS`, `EXTENDS`).
- **`tscode_kg/coderank.py`** — global/personalized weighted PageRank and
  hybrid query ranking utilities, ported from PyCodeKG's schema-agnostic
  `ranking/coderank.py`.

### Fixed

- **Extractor/kg.py imported from `kg_utils.types`**, which doesn't exist in
  the currently published `kgmodule-utils` 0.6.2 (real layout is
  `kg_utils.specs` and `kg_utils.extractor`) — this crashed `import tscode_kg`
  and the `tscodekg` CLI entirely on a clean install.
- **Removed the hard runtime dependency on `pycode_kg`.** `analysis.py`'s
  CodeRank/centrality phases and `mcp_server.py`'s `DEFAULT_MODEL`/
  `DEFAULT_RELS` previously imported from `pycode_kg`, an undeclared
  dependency not installed by any extra; they now use the local
  `centrality.py`/`coderank.py` ports and `kg_utils` directly.
- Dead, unused `from pycode_kg.module.extractor import EdgeSpec, NodeSpec`
  import in `tests/test_extractor.py` that was blocking every extractor test
  from running.
- mypy loop-variable type collision in `analysis.py`'s SIR report renderer
  (`m` reused across two different types in one function scope).
- Two stale assertions in `tests/test_kg.py::test_analyze_returns_markdown`
  that no longer matched the actual report header/table text.
- Stale README/docstring claims: embedding model was `nomic-embed-text-v1.5`
  (actually `BAAI/bge-small-en-v1.5`, the `kgmodule-utils` shared default);
  `KGModule` credited to `pycode-kg` instead of `kgmodule-utils`.
