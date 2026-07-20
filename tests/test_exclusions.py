"""
test_exclusions.py

Tests for directory include/exclude configuration: the [tool.tscodekg]
pyproject.toml loader and TSCodeExtractor's include/exclude filtering.
Adapted from PyCodeKG's test_exclusions.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kg_utils.specs import NodeSpec

from tscode_kg.config import load_exclude_dirs, load_include_dirs
from tscode_kg.extractor import _HAS_TREE_SITTER, TSCodeExtractor

SAMPLE_TS = "export function f(): void {}\n"


@pytest.fixture
def repo_with_dirs(tmp_path: Path) -> Path:
    """Repo with src/, lib/, and scratch/ each holding one .ts file."""
    for d in ("src", "lib", "scratch"):
        f = tmp_path / d / "mod.ts"
        f.parent.mkdir(parents=True)
        f.write_text(SAMPLE_TS)
    return tmp_path


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------


def test_load_include_dirs_no_pyproject(tmp_path: Path) -> None:
    assert load_include_dirs(tmp_path) == set()


def test_load_include_dirs_no_tool_tscodekg(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.other]\nx = 1\n")
    assert load_include_dirs(tmp_path) == set()


def test_load_include_dirs_single_include(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[tool.tscodekg]\ninclude = ["src"]\n')
    assert load_include_dirs(tmp_path) == {"src"}


def test_load_include_dirs_multiple_includes(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[tool.tscodekg]\ninclude = ["src", "lib"]\n')
    assert load_include_dirs(tmp_path) == {"src", "lib"}


def test_load_include_dirs_strips_trailing_slashes(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[tool.tscodekg]\ninclude = ["src/"]\n')
    assert load_include_dirs(tmp_path) == {"src"}


def test_load_include_dirs_invalid_toml(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("not [ valid toml")
    assert load_include_dirs(tmp_path) == set()


def test_load_include_dirs_non_list_include(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[tool.tscodekg]\ninclude = "src"\n')
    assert load_include_dirs(tmp_path) == set()


def test_load_exclude_dirs(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[tool.tscodekg]\nexclude = ["__tests__"]\n')
    assert load_exclude_dirs(tmp_path) == {"__tests__"}


# ---------------------------------------------------------------------------
# Extractor filtering
# ---------------------------------------------------------------------------


def _module_paths(extractor: TSCodeExtractor) -> set[str]:
    return {
        item.source_path
        for item in extractor.extract()
        if isinstance(item, NodeSpec) and item.kind == "module"
    }


@pytest.mark.skipif(not _HAS_TREE_SITTER, reason="tree-sitter-typescript not installed")
def test_extract_no_include_indexes_all(repo_with_dirs: Path) -> None:
    mods = _module_paths(TSCodeExtractor(repo_with_dirs))
    assert len(mods) == 3


@pytest.mark.skipif(not _HAS_TREE_SITTER, reason="tree-sitter-typescript not installed")
def test_extract_with_include_one_dir(repo_with_dirs: Path) -> None:
    mods = _module_paths(TSCodeExtractor(repo_with_dirs, include={"src"}))
    assert mods == {"src/mod.ts"}


@pytest.mark.skipif(not _HAS_TREE_SITTER, reason="tree-sitter-typescript not installed")
def test_extract_with_include_two_dirs(repo_with_dirs: Path) -> None:
    mods = _module_paths(TSCodeExtractor(repo_with_dirs, include={"src", "lib"}))
    assert mods == {"src/mod.ts", "lib/mod.ts"}


@pytest.mark.skipif(not _HAS_TREE_SITTER, reason="tree-sitter-typescript not installed")
def test_extract_with_exclude_dir(repo_with_dirs: Path) -> None:
    mods = _module_paths(TSCodeExtractor(repo_with_dirs, exclude={"scratch"}))
    assert mods == {"src/mod.ts", "lib/mod.ts"}


@pytest.mark.skipif(not _HAS_TREE_SITTER, reason="tree-sitter-typescript not installed")
def test_extract_include_nonexistent_dir(repo_with_dirs: Path) -> None:
    mods = _module_paths(TSCodeExtractor(repo_with_dirs, include={"nope"}))
    assert mods == set()
