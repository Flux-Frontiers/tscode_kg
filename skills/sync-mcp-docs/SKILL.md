---
name: sync-mcp-docs
description: Synchronize all TypeScriptKG MCP documentation with the runtime tool API in src/tscode_kg/mcp_server.py — the module docstring "Tools" list, the FastMCP instructions block, README.md, and the tscodekg skill files. This is a required project rule; any change to MCP tool signatures, parameters, defaults, or behavior must ship with matching doc updates in the same commit. Use this skill when the user says: "sync the MCP docs", "update the tool descriptions", "the mcp_server docstring is stale", "keep the FastMCP instructions in sync", "I added/renamed/removed an MCP tool", or after any edit to @mcp.tool() functions in mcp_server.py.
---

# Sync MCP Documentation

You are updating all TypeScriptKG MCP documentation and provider instructions to reflect the current state of `src/tscode_kg/mcp_server.py`. Execute the following steps in order.

> **Project rule (from CLAUDE.md):** Any change to MCP tool signatures, parameters, defaults, or behavior in `src/tscode_kg/mcp_server.py` must include a matching update to the `mcp = FastMCP(..., instructions=(...))` tool descriptions **in the same commit**. Keep the module docstring "Tools" list and the `FastMCP` instructions block aligned with the runtime tool API.

---

## Step 0: Establish the Source of Truth

Read `src/tscode_kg/mcp_server.py` and extract the **authoritative tool list**:

1. Find every `@mcp.tool()` decorated function — these are the live MCP tools.
2. For each tool, record:
   - **Name** and **signature** (function name + parameters with defaults)
   - **One-line description** from the first line of its docstring
   - **Return type** (JSON vs Markdown)
   - **When to use** (from the docstring)
3. Print the complete tool inventory before proceeding. This is your ground truth.

**Example format:**
```
TOOL INVENTORY (from mcp_server.py):
  1. query_codebase(q, k, hop, rels, max_nodes, min_score, max_per_module, rerank_mode)
                                             → JSON — hybrid semantic + structural search
  2. pack_snippets(q, k, hop, rels, context, max_lines, ...)
                                             → MD   — source-grounded snippet extraction
  3. callers(node_id, rel, paths)            → JSON — reverse edge lookup / fan-in
  4. get_node(node_id, include_edges)        → JSON — single node + optional neighborhood
  5. graph_stats()                           → MD   — node/edge counts by kind/relation
  6. list_nodes(module_path, kind)           → JSON — filtered node enumeration
  7. find_node(name, kind)                   → JSON — name/qualname substring search
  8. centrality(top, kinds, group_by)        → MD   — SIR PageRank ranking
  ...
  N. snapshot_diff(key_a, key_b)             → JSON — side-by-side snapshot comparison
```

Include every tool present in the file (e.g. `bridge_centrality`, `framework_nodes`, `find_definition_at`, `explain`, `rank_nodes`, `query_ranked`, `explain_rank` once merged) — never work from a remembered list.

---

## Step 1: Sync mcp_server.py's Own Documentation (Required Rule)

These two blocks live in the same file as the tools and MUST match the runtime API exactly:

### 1a. Module docstring "Tools" list

The docstring at the top of `src/tscode_kg/mcp_server.py` has a `Tools` section listing every tool as:

```
tool_name(param, param, ...)
    One-line description.
```

- Every `@mcp.tool()` function must appear, with the exact current parameter list.
- Remove entries for deleted/renamed tools; add entries for new ones, keeping the file's ordering style.

### 1b. `FastMCP(..., instructions=(...))` block

The `mcp = FastMCP(...)` constructor carries an `instructions` string describing the tool surface to connected agents.

- Update tool names, signatures, defaults, and usage guidance to match the inventory.
- Keep the tone and length consistent with the existing block — it is agent-facing prose, not a reference manual.

---

## Step 2: Update Repository Documentation

### 2a. `README.md`

- **"MCP tools" section** — every tool must appear with correct signature and one-line description; update the tool count if stated.
- Add missing tools; update changed signatures; remove phantom tools.

### 2b. `skills/tscodekg/SKILL.md`

- **Frontmatter `description:` field** — the `using the graph_stats / ... MCP tools` slash-separated list must name every tool.
- **"## MCP Tools" and "## CodeRank Tools" tables** — every tool appears with correct signature; add/update/remove rows in place.
- **"### Typical session workflow"** — update numbered steps if the recommended sequence changes.

### 2c. `skills/tscodekg/references/CHEATSHEET.md`

- **"Tools at a Glance" tables** — add/remove rows to match the inventory.
- **Per-tool sections** — a section (or shared section) must exist for every tool; use the existing compact, examples-first style.
- **"Parameter Quick Reference"** — parameter names and defaults must match `mcp_server.py`.

### 2d. `CLAUDE.md` (if present)

Check the repo-root `CLAUDE.md` for MCP tool tables or lists. If found, apply the same updates (tool count, signatures, descriptions) following that file's existing format.

---

## Step 3: Consistency Check

After all edits, verify:

1. **Tool count** — the count in each file matches the actual number of `@mcp.tool()` functions.
2. **Signatures** — every file uses the same parameter names and defaults as `mcp_server.py`.
3. **No phantom tools** — no file references a tool name that no longer exists.
4. **No missing tools** — every tool in `mcp_server.py` appears in every file.
5. **Docstring ↔ instructions parity** — the module docstring "Tools" list and the FastMCP instructions block describe the same surface.

If inconsistencies are found, fix them before proceeding.

---

## Step 4: Stage and Prepare Commit

1. Stage all modified files:
   ```bash
   git add src/tscode_kg/mcp_server.py README.md \
           skills/tscodekg/SKILL.md \
           skills/tscodekg/references/CHEATSHEET.md
   ```
   Add `CLAUDE.md` if it was modified.

2. Write `commit.txt` with a conventional commit message:
   ```
   docs(mcp): sync all provider docs to N-tool MCP surface

   Updated tool inventory: [list added/removed/changed tools]

   Files updated:
   - src/tscode_kg/mcp_server.py: docstring Tools list + FastMCP instructions
   - README.md: ...
   - skills/tscodekg/SKILL.md: ...
   - skills/tscodekg/references/CHEATSHEET.md: ...
   ```

Do **not** run `git commit` — the user commits with `git commit -F commit.txt`.

---

## Completion

After all steps, print a summary:

```
✓ Source of truth: N tools extracted from mcp_server.py
✓ mcp_server.py docstring   — Tools list synced (N tools)
✓ FastMCP instructions      — synced
✓ README.md                 — updated (MCP tools section)
✓ skills/tscodekg/SKILL.md  — updated (frontmatter + tool tables)
✓ references/CHEATSHEET.md  — updated (N tools)

Files staged. Ready to commit with: git commit -F commit.txt
```

---

## Rules

- **mcp_server.py is always the source of truth.** Never invent tool names or parameters.
- **The docstring + FastMCP instructions sync is mandatory** — it is a project rule, not optional polish.
- **Preserve each file's style.** Don't homogenize formats across files.
- **Minimal diffs.** Only change what is wrong or missing; don't rewrite sections that are correct.
- **Compact style in SKILL.md** (one line per tool in tables); **examples style in CHEATSHEET.md** (actual call syntax).
