# Release Notes — v0.2.0

> Released: 2026-07-29

The first release of TypeScriptKG since the initial cut, and it carries two breaking
changes: the vector store moves from LanceDB to sqlite-vec, and the `kg` extra is dissolved
into the core dependencies. Both simplify installation — but both require action if you
already depend on this package. At 0.x, breaking changes travel in a minor bump.

## What changed

**Breaking: `tscode-kg[kg]` is no longer a valid install target.** `kgmodule-utils[semantic,
sqlite-vec]`, `mcp`, and `networkx` moved from the `kg` extra into core dependencies. Use
plain `tscode-kg`.

The split had stopped making sense. `[project.scripts]` advertised `tscodekg-mcp`
unconditionally while the package it needs sat behind an extra, so a base install handed
you a command that could not possibly run. That could not be repaired by promoting `mcp`
alone either — `mcp_server.py` also imports `kg_utils.semantic` and `tscode_kg.kg` at module
scope, so a base install would simply have failed on a different import. It also left
TypeScriptKG the odd one out: every sibling KG carries `mcp` in core, and PyCodeKG — the
repo this one is modelled on — has no such extra at all. The cost is that a base install now
pulls the sentence-transformers/torch stack. `kgdeps`, `viz`, `viz3d` and `dev` are
unchanged.

**Breaking: vector store migrated from LanceDB to sqlite-vec.** Vectors now live in a single
`.tscodekg/vectors.sqlite` file, mirroring the PyCodeKG and DocKG refactor, and
`TypeScriptKG(...)` takes `vectors_path` where it previously took `lancedb_dir`. **Run
`tscodekg build` once after upgrading.**

**`mcp` bounded below 2.0, with tests that enforce it.** mcp 2.0 removed the bundled
`mcp.server.fastmcp` module, and since the server builds its `FastMCP` instance and
registers all nineteen tools at module import, an unbounded floor let a clean install break
`tscodekg-mcp` at import time. The new `tests/test_mcp_server.py` catches that in CI —
which it now genuinely does: the test previously skipped there, because CI installs
`--extras dev` and `mcp` lived in the `kg` extra it never installed.

**New analysis surface.** Structural Importance Ranking and weighted PageRank
(`centrality.py`, `coderank.py`), the `callers` and `centrality` MCP tools, `tscodekg
analyze`, temporal snapshots with `save`/`list`/`show`/`diff`, `tscodekg init` for
one-command setup, and `tscodekg install-hooks`. The type checker moved from mypy to
[ty](https://github.com/astral-sh/ty).

## Upgrading

Install plain `tscode-kg` — drop any `[kg]` from your dependency spec, or the install will
fail on an unknown extra. Then run `tscodekg build` once to regenerate the vector index in
the new sqlite-vec format; the old `lancedb/` directory can be deleted afterwards. If you
construct `TypeScriptKG` directly, rename `lancedb_dir` to `vectors_path`.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
