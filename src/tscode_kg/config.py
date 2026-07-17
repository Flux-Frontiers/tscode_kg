"""
config.py — Configuration utilities for TypeScriptKG.

Reads include/exclude directory lists from pyproject.toml [tool.tscodekg].
"""

from __future__ import annotations

import tomllib
from pathlib import Path


def _load_dir_list(repo_root: Path | str, key: str) -> set[str]:
    repo_root = Path(repo_root)
    pyproject_path = repo_root / "pyproject.toml"
    if not pyproject_path.exists():
        return set()
    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, ValueError):
        return set()
    value = data.get("tool", {}).get("tscodekg", {}).get(key, [])
    if isinstance(value, list):
        return {d.rstrip("/") for d in value if isinstance(d, str)}
    return set()


def load_include_dirs(repo_root: Path | str) -> set[str]:
    """Return top-level dirs to include (empty = all)."""
    return _load_dir_list(repo_root, "include")


def load_exclude_dirs(repo_root: Path | str) -> set[str]:
    """Return extra dir names to exclude at every depth."""
    return _load_dir_list(repo_root, "exclude")
