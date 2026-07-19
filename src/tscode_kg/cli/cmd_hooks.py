"""
cli/cmd_hooks.py — tscodekg install-hooks command.

  install-hooks — install the pre-commit snapshot hook into .git/hooks/
"""

from __future__ import annotations

import stat
from pathlib import Path

import click

# ---------------------------------------------------------------------------
# Hook script content (embedded so this module is self-contained when
# installed as a package in any repo, not just tscode_kg itself)
# ---------------------------------------------------------------------------

_PRE_COMMIT_HOOK = """\
#!/usr/bin/env bash
# TypeScriptKG pre-commit hook — keeps the local index in sync and captures
# metrics snapshots BEFORE quality checks run.
# Installed by: tscodekg install-hooks
# Skip with: TSCODEKG_SKIP_SNAPSHOT=1 git commit ...
set -euo pipefail

[ "${TSCODEKG_SKIP_SNAPSHOT:-0}" = "1" ] && exit 0

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# Resolve the tscodekg binary: prefer the repo's .venv, fall back to PATH.
if [ -x "$REPO_ROOT/.venv/bin/tscodekg" ]; then
    TSCODEKG="$REPO_ROOT/.venv/bin/tscodekg"
elif command -v tscodekg &>/dev/null; then
    TSCODEKG="tscodekg"
else
    echo "[tscodekg] binary not found — skipping snapshot hook" >&2
    exit 0
fi

# Capture the tree hash of the staged index NOW — before any tool modifies files.
TREE_HASH=$(git write-tree)
BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Rebuild the local index to keep it in sync with staged content.
"$TSCODEKG" build --repo "$REPO_ROOT" || exit 1

# Snapshot TypeScriptKG (version auto-detected from installed package).
"$TSCODEKG" snapshot save \\
    --repo . \\
    --tree-hash "$TREE_HASH" \\
    --branch "$BRANCH" \\
  || { echo "[tscodekg] snapshot skipped (run 'tscodekg build' to initialize)" >&2; }

# Stage the snapshot directory so it is included in the commit.
git add .tscodekg/snapshots/ 2>/dev/null || true

# Run pre-commit framework checks (ruff, ty, detect-secrets, etc.) AFTER
# snapshots are captured and staged. Delegates to .pre-commit-config.yaml so
# quality checks stay in one place.
PRECOMMIT="$REPO_ROOT/.venv/bin/pre-commit"
if [ -x "$PRECOMMIT" ]; then
    "$PRECOMMIT" run || exit 1
elif command -v pre-commit &>/dev/null; then
    pre-commit run || exit 1
fi

exit 0
"""


@click.command("install-hooks")
@click.option(
    "--repo",
    default=".",
    type=click.Path(exists=True),
    show_default=True,
    help="Repository root.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite an existing pre-commit hook.",
)
def install_hooks(repo: str, force: bool) -> None:
    """Install the TypeScriptKG pre-commit git hook.

    After installation, before each commit:

    \b
      1. Rebuilds the local TypeScriptKG index (full wipe)
      2. Captures a metrics snapshot keyed by tree hash
      3. Stages the snapshot directory atomically
      4. Runs the pre-commit framework checks

    This keeps the index in sync and ensures snapshots reflect the state of
    the knowledge graph at commit time.

    Example:
        tscodekg install-hooks --repo .
    """
    repo_root = Path(repo).resolve()
    git_dir = repo_root / ".git"

    if not git_dir.is_dir():
        click.echo(f"Error: {repo_root} is not a git repository.", err=True)
        raise SystemExit(1)

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    hook_path = hooks_dir / "pre-commit"

    if hook_path.exists() and not force:
        click.echo(f"Hook already exists: {hook_path}")
        click.echo("Use --force to overwrite.")
        raise SystemExit(1)

    hook_path.write_text(_PRE_COMMIT_HOOK)
    mode = hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    hook_path.chmod(mode)

    click.echo(f"OK Installed pre-commit hook: {hook_path}")
    click.echo("  Snapshots will be captured automatically before each commit.")
    click.echo("  Run 'tscodekg build' first if you haven't built the graph yet.")
