# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Agent Identity


Always use the TypeScriptKG MCP tools before reading files. You have direct, source-grounded access to this codebase — use it.

---

## Project Overview

**Name:** tscode_kg
**Description:** A tool that indexes TypeScript/JavaScript codebases into a knowledge graph and exposes it via MCP for AI agents
**Stack:** Python/Poetry (tree-sitter extraction, kgmodule-utils SDK)
**Status:** In development

---

## Partnership & Values

**CRITICAL PRINCIPLE:** Consistency is essential. Every decision, pattern, and structure must maintain alignment across the codebase — and with PyCodeKG, the reference implementation of the KG-module approach. Inconsistency creates confusion, technical debt, and friction.

**Our Goal:** Write the cleanest, most efficient, beautiful code possible. Not just functional—exceptional.

---

## TypeScriptKG Toolkit

You have direct access to TypeScriptKG's full power through **two interfaces**:

### MCP Tools (Query the Live Index)
Always use these first — they're faster and source-grounded:

| Tool | Purpose | Example |
|------|---------|---------|
| `graph_stats` | View node/edge counts by kind/relation | Understand graph structure |
| `query_codebase(q, k, hop, rels, max_nodes, min_score, max_per_module)` | Hybrid semantic + structural query with precision/diversity controls | "authentication middleware" |
| `pack_snippets(q, k, hop, ...)` | Extract source-grounded code snippets | Get relevant code for LLM analysis |
| `get_node(node_id)` | Fetch a single node by stable ID | Precise node lookup |
| `callers(node_id, rel)` | Find all callers of a function, resolving cross-module `sym:` stubs | Understand call graph |
| `centrality(top, kinds, group_by)` | SIR PageRank — rank nodes or modules by structural importance | Identify hotspots before refactoring |
| `bridge_centrality(top)` | Module connectivity — orchestrator/hub modules | Understand coupling |
| `framework_nodes(top)` | SIR + connectivity — repo-defining hub modules | Architecture review |
| `explain(node_id)` | Natural-language explanation of a node | Understand a symbol's role |
| `find_definition_at(file, line)` | Reverse-resolve a source location to a node | IDE-style lookup |
| `rank_nodes` / `query_ranked` / `explain_rank` | CodeRank global and query-conditioned ranking | Prioritized exploration |
| `snapshot_list` / `snapshot_show` / `snapshot_diff` | Temporal metric snapshots | Track codebase evolution |

### CLI Commands (Build & Explore Locally)
Build or interact with the knowledge graph from the command line.

Each command is available as a `tscodekg <subcommand>` **or** (where noted) a dedicated `tscodekg-<name>` script — both forms are equivalent:

| Subcommand / Script alias | Purpose |
|---------------------------|---------|
| `init` / `tscodekg-init` | One-command setup: download model, build graph, install hooks, snapshot |
| `build` / `tscodekg-build` | SQLite graph + sqlite-vec index in one step (`--graph-only` / `--index-only` to split) |
| `query` / `tscodekg-query` | Run hybrid query over the graph |
| `pack` / `tscodekg-pack` | Generate source-grounded snippet packs |
| `analyze` / `tscodekg-analyze` | Run thorough codebase analysis |
| `explain` | Natural-language explanation of a node |
| `centrality` / `tscodekg-centrality` | SIR structural importance ranking |
| `bridges` | Module connectivity ranking |
| `framework-nodes` | Framework-like hub module detection |
| `snapshot save/list/show/diff/prune` | Temporal metric snapshots |
| `install-hooks` / `tscodekg-install-hooks` | Install pre-commit git hook for automatic snapshots |
| `download-model` / `tscodekg-download-model` | Cache the embedding model for offline use |
| `mcp` / `tscodekg-mcp` | Start MCP server for Claude/Cursor/Continue |

### Quick Examples

```bash
# First-time setup (downloads model, builds graph, installs hooks, snapshots)
tscodekg init --repo .

# Build the knowledge graph
tscodekg build --repo /path/to/ts-repo

# Query the graph
tscodekg query "authentication middleware"

# Generate snippet pack for LLM analysis
tscodekg pack "error handling utilities"

# Run thorough architectural analysis
tscodekg analyze .

# Start MCP server (for IDE integrations)
tscodekg mcp --repo .
```

**Directory Includes:** Configure via `[tool.tscodekg].include` in `pyproject.toml`. When unset, all directories are indexed. See README for details.

For detailed options: `tscodekg <command> --help`

---

## Skills

Repo-local Claude Code skills live in `skills/` (this repo does not commit `.claude/`):

| Skill | Purpose |
|-------|---------|
| `tscodekg` | Install, configure, and use the TypeScriptKG MCP server and CLI |
| `tscodekg-thorough-analysis` | Run and interpret `tscodekg analyze` |
| `setup-tscodekg-mcp` | Wire up `.mcp.json` / IDE configs and verify the server |
| `sync-mcp-docs` | Keep MCP docstrings and instructions in sync (required rule below) |
| `changelog-commit` | Keep-a-Changelog commit workflow |
| `release` | Version bump, changelog, tag, GitHub Release |

---

## Project-Specific Rules

### No Time Estimates
All plans, roadmaps, and task breakdowns MUST omit time estimates. Use phases, priorities, complexity ratings, and dependencies instead of dates or durations.

- Prefer `:param:` style docstrings

### MCP Instruction Sync (Required)
- Any change to MCP tool signatures, parameters, defaults, or behavior in `src/tscode_kg/mcp_server.py` must include a matching update to the `mcp = FastMCP(..., instructions=(...))` tool descriptions in the same commit.
- Keep the module docstring "Tools" list and the `FastMCP` instructions block aligned with the runtime tool API.

### PyCodeKG Parity
- TypeScriptKG mirrors PyCodeKG's approach: same MCP tool surface, same CLI conventions, same snapshot/hook workflow, same repo hygiene (pre-commit, detect-secrets, CI). When adding or changing behavior here, check how PyCodeKG does it first and stay consistent unless there is a TS/JS-specific reason to diverge — and document any divergence in the CHANGELOG.
