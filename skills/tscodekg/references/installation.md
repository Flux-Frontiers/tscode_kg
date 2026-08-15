# TypeScriptKG Installation Reference

## Table of Contents
1. [CLI Flags Reference](#cli-flags-reference)
2. [Agent Config Matrix](#agent-config-matrix)
3. [MCP Config Templates](#mcp-config-templates)
4. [Query Strategy Guide](#query-strategy-guide)
5. [Gitignore Recommendations](#gitignore-recommendations)
6. [Smoke-Test Commands](#smoke-test-commands)
7. [Full Troubleshooting Table](#full-troubleshooting-table)

---

## Installation

```bash
pip install tscode-kg                # full KG stack
poetry add tscode-kg                 # Poetry projects
```

Repo: <https://github.com/Flux-Frontiers/tscode_kg>

The `[kg]` extra pulls in `kgmodule-utils[semantic,sqlite-vec]`, `mcp`, and `networkx` — required for build, query, analyze, and the MCP server. The optional `[kgdeps]` extra adds `pycode-kg` and `doc-kg` for cross-KG work. The `[viz]` extra (streamlit, pyvis, plotly) enables `tscodekg viz` and `tscodekg viz-timeline`; the `[viz3d]` extra (pyvista, PyQt5) enables `tscodekg viz3d`.

---

## CLI Flags Reference

### `tscodekg init`

| Flag | Default | Description |
|---|---|---|
| `--repo` | `.` | Repository root |
| `--model` | shared kg_utils default | SentenceTransformer model name |
| `--skip-hooks` | false | Don't install the pre-commit git hook |
| `--skip-snapshot` | false | Don't capture an initial snapshot |
| `--force` | false | Overwrite existing graph data and hook |

### `tscodekg build`

| Flag | Default | Description |
|---|---|---|
| `--repo` | `.` | Repository root |
| `--db` | `<repo>/.tscodekg/graph.sqlite` | SQLite graph path |
| `--vectors` | `<repo>/.tscodekg/vectors.sqlite` | sqlite-vec store path |
| — | — | `build` always wipes; use the separate `update` command for an incremental upsert |
| `--graph-only` | false | Build SQLite graph only; skip vector index |
| `--index-only` | false | Build vector index only; graph must already exist |

> There is **no** `build-sqlite` / `build-index` split — `tscodekg build` does both, and the `--graph-only` / `--index-only` flags select a single stage.

### `tscodekg query`

| Flag | Default | Description |
|---|---|---|
| `Q` (argument) | required | Natural-language query |
| `--repo` | `.` | Repository root |
| `-k` | `8` | Semantic seed count |
| `--hop` | `1` | Graph expansion hops |
| `--max-nodes` | `25` | Maximum nodes returned |
| `--rerank` | `hybrid` | Reranking strategy: `hybrid`, `semantic`, `legacy` |

### `tscodekg pack`

| Flag | Default | Description |
|---|---|---|
| `Q` (argument) | required | Natural-language query |
| `--repo` | `.` | Repository root |
| `-k` | `8` | Semantic seed count |
| `--hop` | `1` | Graph expansion hops |
| `--max-nodes` | `15` | Maximum nodes in pack |
| `--max-lines` | `60` | Maximum lines per snippet |
| `--rerank` | `hybrid` | Reranking strategy |
| `--out` | stdout | Output file path (`.md` or `.json`) |

### `tscodekg analyze`

| Flag | Default | Description |
|---|---|---|
| `REPO_ROOT` (argument) | `.` | Repository to analyze |
| `--db` | `<repo>/.tscodekg/graph.sqlite` | SQLite graph path |
| `--vectors` | `<repo>/.tscodekg/vectors.sqlite` | sqlite-vec store path |
| `--report`, `-o` | stdout | Markdown report output path |
| `--write-centrality` | false | Persist SIR scores to the `centrality_scores` table |

### `tscodekg snapshot`

| Subcommand | Key flags |
|---|---|
| `save [VERSION]` | `--repo`, `--db`, `--snapshots-dir`, `--branch`, `--tree-hash` (branch/hash auto-detected) |
| `list` | `--snapshots-dir`, `--limit`, `--json` |
| `show <KEY>` | `--snapshots-dir` (`KEY` = tree hash or `latest`) |
| `diff <KEY_A> <KEY_B>` | `--snapshots-dir`, `--json` |
| `prune` | `--snapshots-dir`, `--dry-run` |

### `tscodekg install-hooks`

| Flag | Default | Description |
|---|---|---|
| `--repo` | `.` | Repository root |
| `--force` | false | Overwrite an existing pre-commit hook |

Skip the installed hook for a single commit: `TSCODEKG_SKIP_SNAPSHOT=1 git commit ...`

### `tscodekg mcp` / `tscodekg-mcp`

| Flag | Default | Description |
|---|---|---|
| `--repo` | `.` | Repository root |
| `--db` | `.tscodekg/graph.sqlite` | SQLite graph path |
| `--vectors` | `.tscodekg/vectors.sqlite` | sqlite-vec store path |
| `--model` | shared kg_utils default | Sentence-transformer model name |
| `--transport` | `stdio` | `stdio` or `sse` |

### Script aliases

Every subcommand with an alias: `tscodekg-init`, `tscodekg-build`, `tscodekg-query`, `tscodekg-pack`, `tscodekg-analyze`, `tscodekg-centrality`, `tscodekg-viz`, `tscodekg-viz3d`, `tscodekg-viz-timeline`, `tscodekg-install-hooks`, `tscodekg-download-model`, `tscodekg-mcp` — equivalent to the `tscodekg <subcommand>` form, handy in Makefiles and Poetry scripts.

---

## Agent Config Matrix

| Agent | Config file | Key | Per-repo? |
|---|---|---|---|
| **Claude Code** | `.mcp.json` (project root) | `"mcpServers"` | ✅ Yes |
| **Kilo Code** | `.mcp.json` (project root) | `"mcpServers"` | ✅ Yes |
| **GitHub Copilot** | `.vscode/mcp.json` (workspace root) | `"servers"` | ✅ Yes |
| **Claude Desktop** | `~/Library/Application Support/Claude/claude_desktop_config.json` | `"mcpServers"` | ❌ Global |
| **Cline** | `~/...saoudrizwan.claude-dev/settings/cline_mcp_settings.json` | `"mcpServers"` | ❌ Global only |

> ⚠️ **Do NOT add `tscodekg` to any global settings file.** Global files are shared across all windows — hardcoded paths point every window to the same repo. Use per-repo config files. For Cline, use a uniquely-named entry per repo (e.g. `tscodekg-myproject`).

---

## MCP Config Templates

### Claude Code / Kilo Code `.mcp.json`

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

### GitHub Copilot `.vscode/mcp.json`

Different schema — `"servers"` key (not `"mcpServers"`) and `"type": "stdio"` required:

```json
{
  "servers": {
    "tscodekg": {
      "type": "stdio",
      "command": "/absolute/path/to/venv/bin/tscodekg",
      "args": ["mcp", "--repo", "/absolute/path/to/repo"]
    }
  }
}
```

VS Code will prompt you to **Trust** the server on first use.

### Claude Desktop (absolute binary path)

```json
{
  "mcpServers": {
    "tscodekg": {
      "command": "/absolute/path/to/venv/bin/tscodekg",
      "args": [
        "mcp",
        "--repo", "/absolute/path/to/repo",
        "--db",   "/absolute/path/to/repo/.tscodekg/graph.sqlite"
      ]
    }
  }
}
```

Get the binary path: `poetry env info --path` → `<venv>/bin/tscodekg`, or `which tscodekg` in the active environment.

---

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
| `IMPORTS` | Dependency analysis |
| `INHERITS` | Class hierarchy (`class extends class`) |
| `IMPLEMENTS` | Class → interface conformance |
| `EXTENDS` | Interface → interface hierarchy |
| `RESOLVES_TO` | Connecting `sym:` stubs to definitions; used internally by `callers()` |

### Node ID format

`<prefix>:<module_path>:<qualname>`

| Prefix | Kind |
|---|---|
| `mod:` | module |
| `cls:` | class |
| `iface:` | interface |
| `type:` | type alias |
| `enum:` | enum |
| `ns:` | namespace |
| `fn:` | function |
| `meth:` | method |
| `sym:` | unresolved external symbol |

Examples: `cls:src/auth/middleware.ts:AuthMiddleware`, `fn:src/utils/helpers.ts:formatDate`, `iface:src/types/user.ts:UserProfile`.

---

## Gitignore Recommendations

```gitignore
.tscodekg/
```

Un-ignore `.tscodekg/snapshots/` if you want snapshot history tracked in git (the pre-commit hook stages snapshots with each commit).

---

## Smoke-Test Commands

```bash
# Graph stats (Python API)
python -c "
from tscode_kg.kg import TypeScriptKG
import json
kg = TypeScriptKG(repo_root='.')
print(json.dumps(kg.stats(), indent=2))
"

# Sample query (CLI — run from the repo root so .tscodekg/ defaults resolve)
tscodekg query "module structure"

# Verify SQLite row counts
sqlite3 .tscodekg/graph.sqlite "SELECT COUNT(*) FROM nodes; SELECT COUNT(*) FROM edges;"
```

---

## Full Troubleshooting Table

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'mcp'` | Incomplete install | `pip install tscode-kg` |
| `WARNING: SQLite database not found` | Graph not built | `tscodekg build --repo .` |
| Empty results from `query_codebase` | Vector store stale or missing | `tscodekg build --repo . --index-only` |
| `RuntimeError: TypeScriptKG not initialised` | Server not started via CLI | Always start with `tscodekg mcp` / `tscodekg-mcp --repo ...` |
| Snippets show wrong line numbers | Source changed since build | `tscodekg build --repo .` |
| MCP server not in Claude Code / Kilo Code | Relative paths or wrong location | Absolute paths in `.mcp.json` (project root); restart |
| MCP server not in GitHub Copilot | Missing `"type": "stdio"` or wrong key | Use `"servers"` key with `"type": "stdio"` in `.vscode/mcp.json`; click Trust |
| MCP server not in Claude Desktop | Wrong binary path | `poetry env info --path` for the absolute `bin/tscodekg` |
| Pre-commit hook fires when unwanted | Hook installed | `TSCODEKG_SKIP_SNAPSHOT=1 git commit ...` |
| Wrong directories indexed | Includes/excludes unset | `[tool.tscodekg] include = [...]` / `exclude = [...]` in `pyproject.toml`, then rebuild |
| Embedding download fails in CI / air-gapped | No network to HuggingFace | `tscodekg download-model` beforehand and cache the model dir |
