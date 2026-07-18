---
name: setup-tscodekg-mcp
description: Set up and verify the TypeScriptKG MCP server for a target repository — install tscode-kg, build the knowledge graph, smoke-test the query pipeline, and configure MCP clients (.mcp.json for Claude Code / Kilo Code, .vscode/mcp.json for GitHub Copilot, claude_desktop_config.json for Claude Desktop). Use this skill when the user says: "set up tscodekg for this repo", "configure the TypeScriptKG MCP server", "add tscodekg to .mcp.json", "index this TypeScript repo with tscodekg", "get tscodekg working in Claude Code / Claude Desktop / Copilot", or "verify the tscodekg server responds".
---

# TypeScriptKG MCP Setup & Verification

Set up the TypeScriptKG MCP server for a target repository and configure it for use with Claude Code and/or Claude Desktop. Execute the following steps in sequence.

## Argument Handling

This skill accepts an optional repository path argument:

- No argument — Interactive mode; ask for the target repository path
- `/setup-tscodekg-mcp /path/to/repo` — Set up TypeScriptKG MCP for the specified repository

---

## Step 0: Resolve the Target Repository

1. If a path argument was provided, use it as `REPO_ROOT`.
2. If not, ask the user:
   > "Which repository do you want to index with TypeScriptKG? Please provide the absolute path."
3. Verify the path exists and contains at least one TypeScript/JavaScript file:
   ```bash
   find "$REPO_ROOT" \( -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" \) \
     -not -path "*/node_modules/*" -not -path "*/dist/*" -not -path "*/.next/*" | head -5
   ```
4. If no TS/JS files are found, stop and report the issue.

All artifact paths default relative to `REPO_ROOT`:
- `DB_PATH` → `$REPO_ROOT/.tscodekg/graph.sqlite`
- `VECTORS_PATH` → `$REPO_ROOT/.tscodekg/vectors.sqlite`

Do not pass `--db` or `--vectors` flags — the commands default to `.tscodekg/` automatically.

---

## Step 1: Verify TypeScriptKG Installation

Prefer `poetry run` in Poetry projects. If `poetry run` fails with a **Python version conflict** (e.g. "Current Python version is not allowed by the project"), fall back to the `.venv` binaries directly.

```bash
# Try poetry run first
poetry run tscodekg --version 2>&1
```

If that prints a version, set `RUNNER="poetry run"`. Otherwise use the venv binary directly:

```bash
$REPO_ROOT/.venv/bin/tscodekg --version
```

In pip environments, plain `tscodekg --version` suffices. Document which runner was used in the final report.

1. Check that the `tscodekg` entry point resolves:
   ```bash
   $RUNNER tscodekg --version
   ```
2. If not found, check whether the package is installed:
   ```bash
   $RUNNER python -m pip show tscode-kg 2>/dev/null
   ```
3. If missing, instruct the user to install it — **the `[kg]` extra is required** for build/query/MCP:
   ```bash
   pip install "tscode-kg[kg]"
   # or, in Poetry projects:
   poetry add "tscode-kg[kg]"
   ```
   Then stop — the user must install before continuing.

4. Confirm the `mcp` Python package is importable (it comes from the `[kg]` extra):
   ```bash
   $RUNNER python -c "import mcp; print('mcp OK')"
   ```
   If this fails, the `[kg]` extra was not installed — reinstall with `pip install "tscode-kg[kg]"`.

5. Check the TypeScriptKG version:
   ```bash
   $RUNNER python -c "import tscode_kg; print(tscode_kg.__version__)"
   ```

---

## Step 2: Build the Knowledge Graph

TypeScriptKG builds the SQLite graph **and** the sqlite-vec index in one command — there are no separate `build-sqlite` / `build-index` steps.

1. Check whether the graph already exists:
   ```bash
   ls -lh "$REPO_ROOT/.tscodekg/graph.sqlite" 2>/dev/null
   ```
2. If it exists, ask the user:
   > "A knowledge graph already exists at `$REPO_ROOT/.tscodekg/graph.sqlite`. Rebuild it from scratch (wipe), or keep the existing graph?"
   - **Wipe**: proceed with `--wipe`
   - **Keep**: skip to Step 3

3. Run the build:
   ```bash
   $RUNNER tscodekg build --repo "$REPO_ROOT" --wipe
   ```
   (Use `--graph-only` / `--index-only` only if a single stage needs rebuilding.)

4. Verify both artifacts were created and are non-empty:
   ```bash
   sqlite3 "$REPO_ROOT/.tscodekg/graph.sqlite" "SELECT COUNT(*) FROM nodes; SELECT COUNT(*) FROM edges;"
   ls -lh "$REPO_ROOT/.tscodekg/vectors.sqlite"
   ```
5. Report the node and edge counts. If both are zero, warn the user — the repo may have no indexable TS/JS files, or `[tool.tscodekg] include` may be excluding everything.

---

## Step 3: Smoke-Test the Query Pipeline

Run a quick end-to-end test to confirm the full pipeline works before configuring any agent:

1. Graph stats check:
   ```bash
   $RUNNER python -c "
   from tscode_kg.kg import TypeScriptKG
   import json
   kg = TypeScriptKG(repo_root='$REPO_ROOT')
   print(json.dumps(kg.stats(), indent=2))
   "
   ```

2. Sample query (run from `$REPO_ROOT` so `.tscodekg/` defaults resolve):
   ```bash
   cd "$REPO_ROOT" && $RUNNER tscodekg query "module structure"
   ```

3. Verify the MCP server starts and announces its config (Ctrl-C after the banner):
   ```bash
   cd "$REPO_ROOT" && timeout 10 $RUNNER tscodekg mcp --repo "$REPO_ROOT" </dev/null || true
   # Expect stderr banner: "TypeScriptKG MCP server starting" with repo/db/vectors/model/transport
   # and NO "WARNING: SQLite database not found"
   ```

4. If any command errors, diagnose and report the issue before proceeding.

---

## Step 4: Configure MCP Clients

The TypeScriptKG MCP server is started with `tscodekg mcp --repo <REPO_ROOT>` (transport `stdio` by default; `--transport sse` for HTTP clients). Always use absolute paths.

### MCP config by agent — quick reference

| Agent | Config file | Per-repo? | Key name |
|-------|-------------|-----------|----------|
| **Claude Code** | `.mcp.json` (project root) | ✅ Yes | `"mcpServers"` |
| **Kilo Code** | `.mcp.json` (project root) | ✅ Yes | `"mcpServers"` |
| **GitHub Copilot** | `.vscode/mcp.json` | ✅ Yes | `"servers"` |
| **Claude Desktop** | `~/Library/Application Support/Claude/claude_desktop_config.json` | ❌ Global only | `"mcpServers"` |
| **Cline** | `~/...saoudrizwan.claude-dev/settings/cline_mcp_settings.json` | ❌ Global only | `"mcpServers"` |

> ⚠️ **Do NOT add `tscodekg` to any global settings file.** Global files are shared across all windows — hardcoded paths point every window to the same repo. Use per-repo config files. For Cline, use a uniquely-named entry per repo (e.g. `tscodekg-myproject`).

### 4a: Claude Code / Kilo Code (.mcp.json)

1. Check if `.mcp.json` exists in `$REPO_ROOT`:
   ```bash
   cat "$REPO_ROOT/.mcp.json" 2>/dev/null
   ```
2. If an existing `tscodekg` entry is found under `mcpServers`, ask the user to replace or keep it.
3. Resolve the binary path (`which tscodekg` in the active environment, or `poetry env info --path` → `<venv>/bin/tscodekg`).
4. The entry to add/update:
   ```json
   "tscodekg": {
     "command": "<abs_path>/tscodekg",
     "args": ["mcp", "--repo", "<REPO_ROOT>"]
   }
   ```
5. Merge into the existing `mcpServers` object — do not overwrite other entries.
6. Verify no `tscodekg` entry exists in global settings (`~/.claude/settings.json`, Kilo Code `mcp_settings.json`); remove it if found.

### 4b: GitHub Copilot (.vscode/mcp.json)

Uses the `"servers"` key and requires `"type": "stdio"`:

```json
{
  "servers": {
    "tscodekg": {
      "type": "stdio",
      "command": "<abs_path>/tscodekg",
      "args": ["mcp", "--repo", "<REPO_ROOT>"]
    }
  }
}
```

Merge into the existing `servers` object. After saving, VS Code prompts you to trust the MCP server — click **Trust**.

### 4c: Claude Desktop (claude_desktop_config.json)

Claude Desktop does not inherit shell PATH — use the absolute binary path.

Config path:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
"tscodekg": {
  "command": "<abs_path>/tscodekg",
  "args": ["mcp", "--repo", "<REPO_ROOT>"]
}
```

Merge into the existing `mcpServers` object.

### 4d: Optional Extras

- Install the pre-commit snapshot hook: `$RUNNER tscodekg install-hooks --repo "$REPO_ROOT"` (skip per-commit with `TSCODEKG_SKIP_SNAPSHOT=1`).
- Add `.tscodekg/` to the repo's `.gitignore` if not already there.
- Copy the `tscodekg` skill (this repo's `skills/tscodekg/`) to `~/.claude/skills/tscodekg/` so all sessions get expert TypeScriptKG knowledge.

---

## Step 5: Final Report

Present a summary of everything that was done:

```
✓ TypeScriptKG version:  <version>
✓ Runner used:           poetry run / pip env / .venv/bin/tscodekg
✓ Repository indexed:    <REPO_ROOT>
✓ SQLite graph:          <REPO_ROOT>/.tscodekg/graph.sqlite  (<N> nodes, <M> edges)
✓ sqlite-vec index:      <REPO_ROOT>/.tscodekg/vectors.sqlite
✓ Smoke test:            passed (query + server banner)
✓ Claude Code config:    <REPO_ROOT>/.mcp.json  (tscodekg entry)
✓ Claude Desktop config: <CONFIG_PATH>  (tscodekg entry / skipped)

Restart Claude Code / Claude Desktop to activate the tscodekg MCP server.

Available tools once active:
  • graph_stats()                — codebase size and shape
  • query_codebase(q)            — semantic + structural exploration
  • pack_snippets(q)             — source-grounded code snippets
  • get_node(node_id)            — single node metadata + neighborhood
  • list_nodes(module_path, kind) — enumerate nodes in a module
  • find_node(name, kind)        — locate nodes by name
  • find_definition_at(path, line) — definition at a file:line position
  • callers(node_id)             — fan-in lookup
  • explain(node_id)             — natural-language node orientation
  • centrality(top) / bridge_centrality(top) / framework_nodes(top)
                                 — structural importance rankings
  • rank_nodes / query_ranked / explain_rank — CodeRank tools
  • analyze_repo()               — full architectural analysis
  • snapshot_list / snapshot_show / snapshot_diff — temporal tracking

Suggested first query after restart:
  graph_stats()
```

---

## Important Rules

- **Do NOT modify source files** in the target repository.
- **Do NOT run `git commit`** or any destructive git operations.
- Use **absolute paths** everywhere — relative paths will break MCP clients.
- The `mcp` package comes from the **`[kg]` extra** — install `tscode-kg[kg]`, not bare `tscode-kg`.
- If any step fails, stop and report the error clearly before proceeding.
- If the user's repo is very large, warn that the build and embedding steps take a while on first run (model download + embedding).

| Error | Fix |
|-------|-----|
| `tscodekg: command not found` | `pip install "tscode-kg[kg]"` or use the absolute venv binary |
| `Current Python version is not allowed by the project` | Use `.venv/bin/tscodekg` directly instead of `poetry run tscodekg` |
| `ModuleNotFoundError: No module named 'mcp'` | Install the extra: `pip install "tscode-kg[kg]"` |
| `WARNING: SQLite database not found` | Run `tscodekg build --repo "$REPO_ROOT"` first |
| Empty query results | `tscodekg build --repo "$REPO_ROOT" --index-only --wipe` |
| Server not appearing in Claude Code | Absolute binary path in `.mcp.json`; restart Claude Code |
| `Command not found` in VS Code MCP log | Extension host doesn't inherit shell PATH — use the absolute binary path |

---

## Rebuilding After Code Changes

When the target codebase changes, the graph must be rebuilt:

```bash
$RUNNER tscodekg build --repo "$REPO_ROOT" --wipe
```

The MCP client configs do not need to change — they point to the same file paths.
