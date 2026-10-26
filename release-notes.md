# Release Notes -- v0.8.0

> Released: 2026-10-26

TSCodeKG's MCP server now runs on the fleet's shared base, `kg_utils.mcp`, so
its first five tools have the same names on every fleet KG server: `stats`,
`query`, `pack`, `get_node` and `neighbors`. Its 15 domain tools are the same
set, in the same order, as PyCodeKG's. Tool names, some arguments and the
shape of `stats()` change, so read Upgrading before you install.

## What changed

**Canonical tool names.** `graph_stats` is `stats`, `query_codebase` is
`query`, `pack_snippets` is `pack`, and `get_node(include_edges=True)` is
`get_node` followed by the new `neighbors`. There are no aliases. `query` and
`pack` keep TypeScriptKG's hybrid reranking and per-module cap, and when
`rels` is omitted they still follow all six relations, including
`IMPLEMENTS` and `EXTENDS`.

**One command, standard flags.** `tscodekg mcp` and `tscodekg-mcp` are the
same command, with `--repo`, `--db`, `--vectors`, `--model`,
`--transport stdio|streamable-http`, `--host`, `--port` and `--manifest`. The
graph opens per session and closes after, and a repository with no graph is
refused instead of served empty. The server's instructions are generated from
the tools' docstrings.

**Statistics in the fleet shape.** `TypeScriptKG.stats()` returns `kind`,
`nodes` (`total`, `by_kind`) and `edges` (`total`, `by_rel`), plus the
module's own measures. Snapshots keep their flat keys.

**Fixed:** `list_nodes` and `find_node` answered "No database store
available" when they were a session's first call. They work now.

## Upgrading

Rename the tools in agent instructions and scripts, pass `rels` as a list,
and drop `format="markdown"` from `query` calls and `--transport sse` from
configs. Code that read `stats()["total_nodes"]` reads `["nodes"]["total"]`
instead. tscode-kg now needs kgmodule-utils 0.29.0, whose `[mcp]` extra brings
the MCP SDK.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
