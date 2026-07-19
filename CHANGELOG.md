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
- **`callers(node_id, rel, paths)` MCP tool** — precise reverse lookup of
  every caller (or subclass/implementer/importer via `rel`) of a node,
  resolving cross-module `sym:` stubs; mirrors PyCodeKG's tool of the same
  name.
- **`centrality(top, kinds, group_by)` MCP tool** — SIR PageRank ranking of
  nodes or modules, backed by the local `centrality.py`; mirrors PyCodeKG's
  tool of the same name.
- **`tscodekg analyze` CLI command** (and `tscodekg-analyze` script alias) —
  runs the 14-phase `TSCodeKGAnalyzer` and emits a Markdown report
  (`--report`, `--write-centrality`), matching `pycodekg analyze`.
- **Temporal snapshots** (`tscode_kg/snapshots.py`) — `SnapshotManager` bound
  to the `tscode-kg` package over the shared `kg_utils.snapshots` base;
  snapshots stored in `.tscodekg/snapshots/{tree_hash}.json` with a manifest,
  mirroring PyCodeKG's `.pycodekg/snapshots/` layout.
- **`tscodekg snapshot` CLI group** — `save` / `list` / `show` / `diff` /
  `prune`, matching `pycodekg snapshot`. `save` runs the analyzer for issue
  counts and hotspots and degrades to a stats-only snapshot when the semantic
  extras are unavailable (so the pre-commit hook works on graph-only builds).
- **`tscodekg install-hooks`** (and `tscodekg-install-hooks`) — installs a
  pre-commit git hook that rebuilds the index, captures a tree-hash-keyed
  snapshot, stages `.tscodekg/snapshots/`, and then runs the pre-commit
  framework checks. Skip per-commit with `TSCODEKG_SKIP_SNAPSHOT=1`.
- **`tscodekg init`** (and `tscodekg-init`) — one-command setup: scaffolds
  `[tool.tscodekg]`, downloads the embedding model, builds the graph,
  installs the hook, and captures an initial snapshot.
- **`tscodekg download-model`** (and `tscodekg-download-model`) — caches the
  embedding model locally for offline builds.
- **`snapshot_list` / `snapshot_show` / `snapshot_diff` MCP tools** with
  freshness metadata vs. the live graph, mirroring PyCodeKG.
- **GitHub Actions CI** (`.github/workflows/ci.yml`: ruff lint + format,
  `ty` type check, pytest excluding integration marks) and **release
  workflow** (`.github/workflows/release.yml`: build wheel/sdist and create
  a GitHub Release from `release-notes.md` on `v*` tags), adapted from
  PyCodeKG.
- **`poetry.toml`** (`virtualenvs.in-project = true`) matching PyCodeKG and
  KG_utils.
- **`tests/test_snapshots.py`** — snapshot capture/save/list/diff round-trip
  tests.
- **`tscode_kg/explain.py`** — shared `render_explain` presenter (metadata,
  JSDoc, callers, callees, kind-aware role labels) backing both the CLI and
  MCP `explain` surfaces; role heuristics adapted to TS/JS (interfaces,
  type-level declarations, JS runtime protocol members).
- **`tscode_kg/bridge.py`** — module connectivity (bridge centrality), and
  **`tscode_kg/framework_detector.py`** — framework-like hub detection
  (0.6 × SIR + 0.4 × connectivity), both ported from PyCodeKG.
- **Seven MCP tools completing PyCodeKG tool parity (19 total)**:
  `bridge_centrality`, `framework_nodes`, `find_definition_at`, `explain`,
  `rank_nodes`, `query_ranked`, `explain_rank` — signatures mirror PyCodeKG
  (rank tools default to the TS relation set incl. IMPLEMENTS/EXTENDS).
- **Four CLI commands**: `explain`, `centrality` (+ `tscodekg-centrality`
  alias), `bridges`, `framework-nodes`.
- **Repo/doc parity**: `CLAUDE.md`, `CITATION.cff`, and a `docs/` set
  (INSTALLATION, MCP, CHEATSHEET, SNAPSHOTS, CODERANK, Analyze,
  pull_request_template) adapted from PyCodeKG.
- **`skills/` directory** with repo-local Claude Code skills: `tscodekg`
  (+ installation/cheatsheet references), `tscodekg-thorough-analysis`,
  `setup-tscodekg-mcp`, `sync-mcp-docs`, `changelog-commit`, `release`.
- **Tests**: `test_centrality.py`, `test_coderank.py`, `test_explain.py`,
  `test_bridge.py`, `test_exclusions.py` adapted from PyCodeKG's suite.
- **Streamlit visualizer** (`tscode_kg/app.py`, `tscodekg viz` +
  `tscodekg-viz`) — port of PyCodeKG's interactive graph explorer over the
  shared `kg_utils` GraphStore, with the TS kind palette (interface,
  type_alias, enum, namespace shapes/colors), IMPLEMENTS/EXTENDS edge colors,
  JSDoc labels, TypeScript snippet highlighting, and `TSCODEKG_DB` /
  `TSCODEKG_VECTORS` env vars. Requires the new `viz` extra
  (streamlit, pyvis, plotly).
- **3-D visualizer** (`tscode_kg/viz3d.py` + `layout3d.py`, `tscodekg viz3d`
  + `tscodekg-viz3d`) — port of the PyVista/PyQt5 Allium & Funnel renderer:
  TS kinds colored/sized/stratified (interfaces share the class layer and
  octahedron LOD geometry), IMPLEMENTS/EXTENDS edge checkboxes and colors,
  interface counts in the stats panel and title bar, and a JSDoc popup that
  parses both `:param:` and `@param` doc styles. Requires the new `viz3d`
  extra (pyvista, PyQt5, pyvistaqt, param, markdown, trame-vtk).
- **Snapshot timeline** (`tscode_kg/viz3d_timeline.py`,
  `tscodekg viz-timeline` + `tscodekg-viz-timeline`) — Plotly 2-D/3-D
  temporal metrics visualization over `.tscodekg/snapshots/`, adapted to the
  dict-based kg_utils snapshot metrics; `tests/test_viz3d_timeline.py`
  ported (20 tests).
- **`pycode-kg>=0.20.0,<0.21` added to the `dev` and `kgdeps` extras** —
  this repo is Python, so a dev checkout needs `pycodekg` for the check-in
  indexing/snapshot workflow. Note this pulls the semantic stack
  (sentence-transformers) into `poetry install --extras dev`; move it out
  if CI install weight becomes a problem.
- **Removed the `[tool.poetry.group.dev.dependencies]` group** — it
  duplicated the PEP-621 `dev` extra entry-for-entry (PyCodeKG has no such
  group either), and every duplicated declaration multiplies Poetry's
  marker-override re-solve rounds during `poetry lock`. Install dev tools
  with `poetry install --extras dev` / `pip install -e ".[dev]"` as before.
- **`viz3d` extra uses plain `pyvista`, not `pyvista[jupyter]`** — the
  jupyter extra's trame/jupyter subtree sends Poetry's resolver into
  runaway marker-split re-solving (the lock never converged). The Qt
  interactor doesn't need it; install `pyvista[jupyter]` manually for
  in-notebook rendering or HTML export. Viz extras carry version brackets
  matching PyCodeKG's proven lockfile versions.

### Fixed

- **Clarified repo self-indexing: this repository is Python, so PyCodeKG —
  not TypeScriptKG — indexes it on commit.** CLAUDE.md now directs agents to
  the PyCodeKG MCP tools for exploring this codebase (`pycodekg init --repo .`
  installs the hook), `[tool.pycodekg] include = ["src"]` was added to
  pyproject.toml, `.gitignore` ignores `.pycodekg/` artifacts while keeping
  `.pycodekg/snapshots/` committable, and the pre-commit large-file and
  detect-secrets excludes cover both `.tscodekg/` and `.pycodekg/`.
  `tscodekg install-hooks` remains the product feature for TS/JS repos.
- **MCP `analyze_repo` wrote Rich phase output to stdout**, which carries the
  MCP protocol on the stdio transport; the analyzer now runs against a silent
  console (matching PyCodeKG) and falls back to a stats-only report instead
  of re-running the noisy analyzer.
- **`.gitignore` ignored `.tscodekg/snapshots/` and `**/.tscodekg/`
  wholesale**, which would have made the pre-commit hook's
  `git add .tscodekg/snapshots/` a silent no-op. Now only generated
  artifacts (graph/vectors SQLite, models, lancedb leftovers) are ignored
  and snapshots are committable, matching PyCodeKG.
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
