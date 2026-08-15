# Installation & Configuration

Full installation options, manual MCP setup, and CLI reference for TypeScriptKG.

---

## Requirements

Python ≥ 3.12, < 3.14

TypeScriptKG is a Python tool: it indexes TypeScript/JavaScript repositories (`.ts`, `.tsx`, `.js`, `.jsx`, `.mts`, `.cts`, `.mjs`, `.cjs`) via tree-sitter, but installs and runs as a Python package.

---

## Install via pip

```bash
# Everything: tree-sitter extraction, SQLite graph, sqlite-vec index,
# hybrid query, and the MCP server
pip install tscode-kg
```

---

## Install via Poetry

```bash
poetry add tscode-kg
```

Or in `pyproject.toml`:

```toml
[tool.poetry.dependencies]
tscode-kg = ">=0.1.0"
```

> **Cross-KG tooling:** the `kgdeps` extra was removed in 0.3.0. It declared
> `pycode-kg` and `doc-kg`, which TypeScriptKG never imports — the `pycodekg`
> CLI indexes this repo from the outside via the pre-commit hook. Those are now
> a Poetry group, installed only by contributors and absent from the published
> package:
>
> ```bash
> poetry install --with kg
> ```

> **TypeScriptKG developers:** Use `poetry install --with dev`. Dev tooling is a
> Poetry group, not an extra — it never ships in the wheel, so `pip install
> ".[dev]"` has nothing to resolve. The `extras` below are for *consumers*.

### Extras

| Extra | Contents |
|---|---|
| `viz` | `streamlit`, `pyvis`, `plotly` — interactive graph explorer and snapshot timeline |
| `viz3d` | `pyvista`, `PyQt5`, `pyvistaqt`, `param`, `markdown`, `trame-vtk` — 3-D visualizer |

`kgmodule-utils[semantic,sqlite-vec]`, `mcp` and `networkx` are **core**
dependencies, not an extra — the semantic index, hybrid query and MCP server
are always available.

### Poetry groups

| Group | Install | Contents |
|---|---|---|
| `dev` | `poetry install --with dev` | `ruff`, `ty`, `pylint`, `pytest`, `pytest-cov`, `pre-commit`, `detect-secrets` |
| `kg` | `poetry install --with kg` | the `pycodekg` and `dockg` CLIs this repo runs |

Groups are locked and installable but never written into the wheel, so no
published extra acquires a sibling KG package.

---

## Development Setup

```bash
git clone https://github.com/Flux-Frontiers/tscode_kg.git
cd tscode_kg
poetry install --with dev            # core + dev tools
poetry install --with dev,kg         # + the pycodekg / dockg CLIs
```

Run the test suite:

```bash
pytest
```

---

## CLI Reference

All commands are available as `tscodekg <subcommand>`. The most common subcommands also ship as dedicated `tscodekg-<name>` scripts. Both forms are equivalent.

| Script alias | Equivalent subcommand |
|---|---|
| `tscodekg-init` | `tscodekg init` |
| `tscodekg-build` | `tscodekg build` |
| `tscodekg-query` | `tscodekg query` |
| `tscodekg-pack` | `tscodekg pack` |
| `tscodekg-analyze` | `tscodekg analyze` |
| `tscodekg-centrality` | `tscodekg centrality` |
| `tscodekg-viz` | `tscodekg viz` |
| `tscodekg-viz3d` | `tscodekg viz3d` |
| `tscodekg-viz-timeline` | `tscodekg viz-timeline` |
| `tscodekg-download-model` | `tscodekg download-model` |
| `tscodekg-install-hooks` | `tscodekg install-hooks` |
| `tscodekg-mcp` | `tscodekg mcp` |

The remaining subcommands — `snapshot` (`save` / `list` / `show` / `diff` / `prune`), `bridges`, `framework-nodes`, and `explain` — are available through the `tscodekg` group only.

```bash
tscodekg --help
```

---

## First-Time Setup: `tscodekg init`

One command does everything — scaffolds `[tool.tscodekg]` in `pyproject.toml`, downloads the embedding model, builds the graph, installs the pre-commit hook, and captures an initial snapshot:

```bash
tscodekg init --repo /path/to/ts-repo
```

| Option | Description |
|---|---|
| `--repo` | Repository root (default `.`) |
| `--model` | SentenceTransformer model name (default: shared `kg_utils` default) |
| `--skip-hooks` | Don't install the pre-commit git hook |
| `--skip-snapshot` | Don't capture an initial snapshot |
| `--force` | Overwrite existing graph data and hook |

`init` is idempotent — safe to run more than once.

---

## Build Step-by-Step

### Recommended: Build both databases at once

```bash
tscodekg build --repo /path/to/repo      # full rebuild (wipes)
tscodekg update --repo /path/to/repo     # incremental upsert
```

### Or in stages

TypeScriptKG has a single `build` command; use its flags to build one half at a time:

```bash
# 1. SQLite knowledge graph only
tscodekg build --repo /path/to/repo --graph-only

# 2. sqlite-vec semantic index only (graph must already exist)
tscodekg build --repo /path/to/repo --index-only

# 3. Pre-download the embedding model (offline / CI)
tscodekg-download-model
```

### Verify the build

```bash
tscodekg query "module structure"
```

A non-empty result confirms both the SQLite graph and sqlite-vec index are wired up correctly. For the full MCP smoke test see [MCP.md § Smoke Test](MCP.md#smoke-test).

### Gitignore

Keep the binary artifacts out of version control:

```gitignore
.tscodekg/graph.sqlite
.tscodekg/vectors.sqlite
```

The SQLite graph and sqlite-vec index are transient and rebuildable. Snapshots in `.tscodekg/snapshots/` are tracked in git and committed atomically by the pre-commit hook — do **not** ignore `.tscodekg/` wholesale, or the hook's `git add .tscodekg/snapshots/` becomes a silent no-op.

---

## Restricting Which Directories Are Indexed

By default, TypeScriptKG indexes all TypeScript/JavaScript files in your repository.

Configure includes and excludes in `pyproject.toml`:

```toml
[tool.tscodekg]
include = ["src"]           # top-level dirs to index (empty = all)
exclude = ["__tests__"]     # extra dirs to skip
```

When no `include` is configured, all directories are indexed (excluding `.git`, `node_modules`, `.tscodekg`, and similar infrastructure directories). `tscodekg init` scaffolds this section automatically, detecting `src`, `lib`, or `app` as the likely source root.

---

## `pack` Options

| Option | Default | Description |
|---|---|---|
| `--repo` | `.` | Repository root |
| `-k` | `8` | Top-K semantic seeds |
| `--hop` | `1` | Graph expansion hops |
| `--max-nodes` | `15` | Max nodes returned in pack |
| `--max-lines` | `60` | Max lines per snippet block |
| `--rerank` | `hybrid` | Reranking strategy: `hybrid`, `semantic`, or `legacy` |
| `--out` | — | Output file path (`.md` or `.json`; omit to print) |

---

## MCP Server Setup

### Claude Code / Kilo Code — `.mcp.json`

```json
{
  "mcpServers": {
    "tscodekg": {
      "command": "tscodekg-mcp",
      "args": ["--repo", "."]
    }
  }
}
```

> Use per-repo `.mcp.json` only — do NOT add `tscodekg` to any global settings file.

### GitHub Copilot — `.vscode/mcp.json`

```json
{
  "servers": {
    "tscodekg": {
      "type": "stdio",
      "command": "/absolute/path/to/.venv/bin/tscodekg-mcp",
      "args": [
        "--repo", "/absolute/path/to/repo",
        "--db", "/absolute/path/to/repo/.tscodekg/graph.sqlite",
        "--vectors", "/absolute/path/to/repo/.tscodekg/vectors.sqlite"
      ]
    }
  }
}
```

### Cline (global settings)

Cline does not support per-repo MCP config. Add a uniquely-keyed entry to Cline's global settings file:

**macOS:** `~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

```json
{
  "mcpServers": {
    "tscodekg-my-repo": {
      "command": "/absolute/path/to/venv/bin/tscodekg-mcp",
      "args": ["--repo", "/absolute/path/to/repo"]
    }
  }
}
```

> Do **not** add a `tscodekg` entry without a repo-specific suffix — global settings are shared across all VS Code windows.

### Claude Desktop — `claude_desktop_config.json`

macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "tscodekg": {
      "command": "/absolute/path/to/venv/bin/tscodekg-mcp",
      "args": ["--repo", "/absolute/path/to/repo"]
    }
  }
}
```

Use **absolute paths** — Claude Desktop does not inherit your shell's working directory.

### Server flags

`tscodekg mcp` / `tscodekg-mcp` accept:

| Flag | Default | Description |
|---|---|---|
| `--repo` | `.` | Repository root directory |
| `--db` | `.tscodekg/graph.sqlite` | SQLite knowledge graph path |
| `--vectors` | `.tscodekg/vectors.sqlite` | sqlite-vec vector store path |
| `--model` | shared `kg_utils` default | Sentence-transformer model name |
| `--transport` | `stdio` | MCP transport: `stdio` or `sse` |

### Restarting agents after MCP setup

| Agent | How to restart |
|---|---|
| **Claude Code** | `Cmd+Shift+P` → `Developer: Reload Window` |
| **Cline** | `Cmd+Shift+P` → `Developer: Reload Window` |
| **Kilo Code** | `Cmd+Shift+P` → `Developer: Reload Window` |
| **GitHub Copilot** | `Cmd+Shift+P` → `Developer: Reload Window` |
| **Claude Desktop** | Quit and relaunch |

See [MCP.md](MCP.md) for the full MCP reference including tool schemas, query strategy guide, and troubleshooting.

---

## For Downstream Projects

If your project depends on TypeScriptKG, **do not** redefine the CLI entrypoints in your own `pyproject.toml`.

**Correct: use TypeScriptKG's commands directly**

```bash
poetry run tscodekg build --repo /path/to/repo
poetry run tscodekg query "search term"
```

**Also correct: forward to TypeScriptKG's modules**

```toml
[tool.poetry.scripts]
my-build = "tscode_kg.cli.cmd_build:build"     # ✅
my-mcp   = "tscode_kg.mcp_server:main"          # ✅
```

Always import from `tscode_kg.cli.*` and `tscode_kg.mcp_server` — the canonical entrypoints defined in `[project.scripts]`.

---

## Output Artifacts

| Artifact | Description |
|---|---|
| `.tscodekg/graph.sqlite` | Canonical knowledge graph (nodes + edges) |
| `.tscodekg/vectors.sqlite` | Derived sqlite-vec semantic index |
| `.tscodekg/snapshots/` | Temporal metric snapshots (tracked in git) |
| Markdown | Human-readable context packs with line numbers |
| JSON | Structured payload for agent/LLM ingestion |
