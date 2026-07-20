---
name: release
description: Cut a versioned release of tscode-kg — promote the [Unreleased] section of CHANGELOG.md into a dated version entry, bump the version in pyproject.toml and src/tscode_kg/__init__.py, write release-notes.md, commit, tag v<version>, and push the tag so .github/workflows/release.yml builds the wheel/sdist and creates the GitHub Release. Use this skill when the user says: "cut a release", "release a new version", "bump the version and tag", "/release patch|minor|major", "promote the changelog", "ship v0.x.y", or "publish a GitHub release for tscode-kg".
---

# Release Workflow

You will create a new versioned release by promoting the `[Unreleased]` section of `CHANGELOG.md` into a dated version entry, writing `release-notes.md`, committing the changes, tagging the commit, and pushing the tag to the remote. Pushing a `v*` tag triggers `.github/workflows/release.yml`, which builds the wheel and sdist with Poetry and creates the GitHub Release (titled `TypeScriptKG v<version>`) with `release-notes.md` as the release notes. Execute the following steps in sequence.

---

## Step 0: Gather Release Context

1. Read `CHANGELOG.md` in full.
2. Read `pyproject.toml` (the `version = "..."` field under `[project]`) and `src/tscode_kg/__init__.py` (`__version__`) to find the current version string.
3. Run `git status` and `git log --oneline -10` to understand the state of the working tree. The tree should be clean apart from release files; if unrelated changes are pending, stop and ask.
4. Confirm there is content under `## [Unreleased]`; if the section is empty, stop and tell the user there is nothing to release.

---

## Step 1: Determine the New Version

1. Parse the current version from `pyproject.toml` (e.g. `0.1.0`).
2. Ask the user which semver component to bump — **patch**, **minor**, or **major** — unless they already specified it (e.g. `/release minor`).
3. Compute the new version string (e.g. `0.1.0` → `0.2.0` for minor).
4. Confirm the new tag will be `v<new_version>` (e.g. `v0.2.0`).

---

## Step 2: Update CHANGELOG.md

1. Replace `## [Unreleased]` with `## [<new_version>] - <today's date in YYYY-MM-DD>`.
2. Insert a fresh `## [Unreleased]` section with empty `### Added`, `### Changed`, `### Removed`, `### Fixed` subsections **above** the newly-versioned section.
3. Write the updated file.

---

## Step 3: Bump the Version in Source Files

Update the version string in **both** of the following files:

- `pyproject.toml` — the `version = "..."` field under `[project]` (PEP 621 table, not `[tool.poetry]`)
- `src/tscode_kg/__init__.py` — the `__version__` assignment

Set both to the new version string (without the `v` prefix).

---

## Step 4: Write release-notes.md

Create (or overwrite) `release-notes.md` in the project root. The release workflow passes this file verbatim to `gh release create --notes-file release-notes.md`, so its content becomes the GitHub Release body:

```markdown
# Release Notes — v<new_version>

> Released: <today's date in YYYY-MM-DD>

<copy the full content of the promoted [Unreleased] section verbatim — all subsections and bullet points>

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
```

Do not summarise or rewrite the changelog content — copy it exactly.

---

## Step 4b: Pre-Release Sanity Checks

1. Run the test suite: `poetry run pytest` (or `pytest` in a pip env). Stop on failures.
2. Verify the package builds locally: `poetry build` — this is exactly what the release workflow runs.
3. If MCP tool signatures changed this cycle, confirm the docs are in sync (see the `sync-mcp-docs` skill) before tagging.

---

## Step 5: Commit the Release Files

1. Stage the following files:
   - `CHANGELOG.md`
   - `release-notes.md`
   - `pyproject.toml`
   - `src/tscode_kg/__init__.py`
2. Create a commit with message:
   ```
   chore(release): v<new_version> release notes
   ```

---

## Step 6: Create the Git Tag

Run:
```bash
git tag -a v<new_version> -m "v<new_version>"
```

---

## Step 7: Push the Commit and Tag

**Before pushing**, display the tag name and ask the user to confirm:

> Ready to push commit and tag `v<new_version>` to `origin`. This will trigger the Release workflow (build wheel/sdist + create the GitHub Release). Proceed? (yes / no)

If confirmed, run:
```bash
git push origin HEAD
git push origin v<new_version>
```

If the user declines, tell them they can push later with the same commands.

---

## Step 8: Verify the Release Workflow

After pushing the tag:

1. Watch the `Release` workflow run (e.g. `gh run watch` or `gh run list --workflow release.yml -L 1`).
2. On success, verify the release exists with the built assets:
   ```bash
   gh release view v<new_version>
   ```
   Expect: title `TypeScriptKG v<new_version>`, body from `release-notes.md`, and `dist/*` wheel + sdist assets.
3. If the workflow fails, diagnose from the run logs before re-tagging. Note: re-pushing the same tag re-runs the job; if the release already exists the workflow uploads assets with `--clobber` instead of failing.

---

## Completion

After all steps succeed, print a summary:

```
✓ CHANGELOG.md promoted [Unreleased] → [<new_version>] - <date>
✓ release-notes.md written
✓ pyproject.toml + src/tscode_kg/__init__.py bumped to <new_version>
✓ Tests + local build passed
✓ Commit created
✓ Tag v<new_version> created
✓ Commit + tag pushed         (or: ready to push manually)
✓ GitHub Release verified     (TypeScriptKG v<new_version>, wheel + sdist attached)
```
