---
name: sync-mcp-docs
description: Synchronize all TypeScriptKG MCP documentation with the live tool list that `tscodekg mcp --manifest` prints -- README.md, docs/MCP.md, docs/CHEATSHEET.md, CLAUDE.md, AGENTS.md and the tscodekg skill files. The server's own instructions are generated from each tool's docstring, so they never need a hand edit; this skill keeps everything else in step. Use this skill when the user says: "sync the MCP docs", "update the tool descriptions", "the docs list the wrong tools", "I added/renamed/removed an MCP tool", or after any change to a tool in src/tscode_kg/mcp_server.py.
---

# Sync MCP Documentation

You are updating TypeScriptKG's MCP documentation to match the live tool list. Execute the following steps in order.

> **Project rule (from CLAUDE.md, "MCP Tool Docs"):** the server is built on `kg_utils.mcp`. Its instructions are the hand-written `PREAMBLE` in `src/tscode_kg/mcp_server.py` plus one line per tool, generated from each tool's docstring. A tool's docstring *is* its documentation, so a change to a tool's signature, parameters, defaults or behavior updates its docstring in the same commit. Nothing in `mcp_server.py` lists the tools by hand.

---

## Step 0: Establish the Source of Truth

Print the live manifest; it never opens the graph:

```bash
tscodekg mcp --repo . --manifest > /tmp/tscodekg_manifest.json
```

It holds `name`, `kind`, `version`, `canonical` (the fleet's five canonical tools) and `tools`: every tool's `name`, `description` (its docstring) and `input_schema` (parameters with types and defaults), in registration order. From it, record for each tool:

- **Name** and **parameters** (with defaults, from `input_schema`)
- **One-line description** (the first line of `description`)
- **Return type** (JSON vs Markdown, from the docstring)

**Example format:**
```
TOOL INVENTORY (from tscodekg mcp --manifest):
  1. stats()                                    -> JSON -- node/edge counts in the fleet stats shape
  2. query(q, k, hop, rels, max_nodes, ...)     -> JSON -- hybrid semantic + structural search
  3. pack(q, k, hop, rels, context, ...)        -> MD   -- source-grounded snippet extraction
  4. get_node(node_id)                          -> JSON -- single node lookup
  5. neighbors(node_id, rels, direction, limit) -> JSON -- one-hop neighborhood
  6. callers(node_id, rel, paths)               -> JSON -- reverse edge lookup / fan-in
  ...
  N. snapshot_diff(key_a, key_b)                -> JSON -- side-by-side snapshot comparison
```

Never work from a remembered list. The first five tools are canonical: their names are the same on every fleet KG server and must not be renamed here.

If a tool's own docstring is wrong, fix the docstring in `mcp_server.py` first; the server's instructions follow from it.

---

## Step 1: Update Repository Documentation

### 1a. `README.md`

- **"MCP tools" section** -- every tool must appear; update the tool count.

### 1b. `docs/MCP.md` and `docs/CHEATSHEET.md`

- **Tool tables and per-tool sections** -- every tool appears with its current parameters and defaults; add, update or remove rows and sections in place.
- **Tool count** -- the "twenty tools" style counts and the Summary table.

### 1c. `skills/tscodekg/SKILL.md`

- **Frontmatter `description:` field** -- the `using the stats / ... MCP tools` slash-separated list must name every tool.
- **"## MCP Tools" and "## CodeRank Tools" tables** -- every tool appears with correct signature; add/update/remove rows in place.
- **"### Typical session workflow"** -- update numbered steps if the recommended sequence changes.

### 1d. `skills/tscodekg/references/CHEATSHEET.md`

- **"Tools at a Glance" tables** -- add/remove rows to match the inventory.
- **Per-tool sections** -- a section (or shared section) must exist for every tool; use the existing compact, examples-first style.
- **"Parameter Quick Reference"** -- parameter names and defaults must match the manifest.

### 1e. `CLAUDE.md` and `AGENTS.md`

Both carry the same MCP tool table; apply the same updates following their existing format.

---

## Step 2: Consistency Check

After all edits, verify:

1. **Tool count** -- the count in each file matches `len(manifest["tools"])`. `tests/test_mcp_server.py` asserts the same number.
2. **Signatures** -- every file uses the parameter names and defaults in the manifest's `input_schema`.
3. **No phantom tools** -- no file references a tool name that is not in the manifest.
4. **No missing tools** -- every tool in the manifest appears in every file.
5. **Tests** -- `pytest tests/test_mcp_server.py` passes, including the parity check against PyCodeKG's canonical tools.

If inconsistencies are found, fix them before proceeding.

---

## Step 3: Stage and Prepare Commit

1. Stage all modified files, for example:
   ```bash
   git add README.md docs/MCP.md docs/CHEATSHEET.md CLAUDE.md AGENTS.md \
           skills/tscodekg/SKILL.md skills/tscodekg/references/CHEATSHEET.md
   ```
   Add `src/tscode_kg/mcp_server.py` if a docstring changed.

2. Write `commit.txt` with a conventional commit message:
   ```
   docs(mcp): sync all provider docs to N-tool MCP surface

   Updated tool inventory: [list added/removed/changed tools]

   Files updated:
   - README.md: ...
   - docs/MCP.md: ...
   - skills/tscodekg/SKILL.md: ...
   ```

Do **not** run `git commit` -- the user commits with `git commit -F commit.txt`.

---

## Completion

After all steps, print a summary:

```
Source of truth: N tools from tscodekg mcp --manifest
README.md                 -- updated (MCP tools section)
docs/MCP.md, CHEATSHEET   -- updated (N tools)
skills/tscodekg/SKILL.md  -- updated (frontmatter + tool tables)
references/CHEATSHEET.md  -- updated (N tools)
CLAUDE.md, AGENTS.md      -- updated

Files staged. Ready to commit with: git commit -F commit.txt
```

---

## Rules

- **`tscodekg mcp --manifest` is always the source of truth.** Never invent tool names or parameters.
- **Never hand-edit a tool list into `mcp_server.py`.** Its instructions are generated; change a tool's docstring instead.
- **Preserve each file's style.** Don't homogenize formats across files.
- **Minimal diffs.** Only change what is wrong or missing; don't rewrite sections that are correct.
- **Compact style in SKILL.md** (one line per tool in tables); **examples style in CHEATSHEET.md** (actual call syntax).
