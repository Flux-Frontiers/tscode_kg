---
name: changelog-commit
description: Analyze staged git changes in the tscode_kg repository, add a matching Keep-a-Changelog entry to CHANGELOG.md, and prepare a conventional commit message in commit.txt — without executing the commit. Use this skill when the user says: "update the changelog and prep a commit", "changelog commit", "write a changelog entry for these staged changes", "prepare a commit message", "log this change in the CHANGELOG", or after staging work that needs a Keep-a-Changelog Unreleased entry plus a conventional-commit message.
---

# Changelog & Commit Workflow

You will analyze staged git changes, update `CHANGELOG.md`, and prepare a commit message. Execute the following steps in sequence.

## Step 0: Verify Files Are Staged

1. Check if files are already staged with `git status`
2. If no files are staged, remind the user to stage files first:
   - `git add <files>` for specific files
   - `git add -A` for all changes
3. Proceed only after files are staged

## Step 1: Analyze Staged Changes

1. Run `git status` to identify staged files
2. Run `git diff --staged` to examine the actual changes
3. Analyze what has been modified, added, or removed

## Step 2: Update CHANGELOG.md

This repo follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

1. Read the existing `CHANGELOG.md` to understand the format
2. Add the new entry under the `## [Unreleased]` section (create it below the header if missing)
3. Write a changelog entry that:
   - Summarizes the changes concisely but informatively — what changed and why
   - Follows the existing style: bold lead-in for significant items, nested bullets for details
   - Uses the appropriate category subsection: `### Added`, `### Changed`, `### Fixed`, `### Removed`
   - Flags breaking changes explicitly (**BREAKING: ...**) and includes migration notes (e.g. "run `tscodekg build` once after upgrading")
4. Update `CHANGELOG.md` with the new entry
5. **Stage CHANGELOG.md** with `git add CHANGELOG.md` so it is included in the commit

## Step 3: Create Commit Message

1. Draft a commit message following conventional commit format:
   ```
   type(scope): brief summary

   Detailed explanation if needed
   ```

2. Determine the appropriate type:
   - `feat`: New feature
   - `fix`: Bug fix
   - `docs`: Documentation changes
   - `refactor`: Code refactoring
   - `test`: Test changes
   - `chore`: Maintenance tasks
   - `style`: Code style changes
   - `perf`: Performance improvements

3. Write a clear, concise summary (50 chars or less for the first line)
4. Add detailed explanation in the body if needed
5. Save the commit message to `commit.txt` in the project root

## Important Rules

- **Do NOT execute `git commit`** — only prepare the commit message file
- Be thorough in analyzing changes before writing summaries
- Follow the project's existing conventions for both changelog and commits
- Remember the MCP sync rule: if the staged diff touches `src/tscode_kg/mcp_server.py` tool signatures, verify the docstring "Tools" list and FastMCP instructions block were updated in the same diff (see the `sync-mcp-docs` skill) and mention it in the changelog entry
- If `CHANGELOG.md` doesn't exist, note this and skip that step

## Completion

After completing all steps, present:
```
✓ Analyzed staged changes
✓ Updated CHANGELOG.md
✓ Staged CHANGELOG.md
✓ Created commit.txt

Ready to commit with: git commit -F commit.txt
```
