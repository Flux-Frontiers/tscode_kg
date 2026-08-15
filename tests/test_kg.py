"""
test_kg.py — integration tests for TypeScriptKG build pipeline.

Marked as 'integration' because they load the real embedding model.
Run with: pytest -m integration
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tscode_kg.extractor import _HAS_TREE_SITTER
from tscode_kg.kg import TypeScriptKG

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _HAS_TREE_SITTER, reason="tree-sitter-typescript not installed"),
]


@pytest.fixture
def built_kg(tmp_repo: Path, tmp_path: Path) -> TypeScriptKG:
    """Build a full TypeScriptKG from the sample fixture."""
    kg = TypeScriptKG(
        repo_root=tmp_repo,
        db_path=tmp_path / "graph.sqlite",
        vectors_path=tmp_path / "vectors.sqlite",
    )
    kg.build(wipe=True)
    return kg


class TestBuildStats:
    def test_build_returns_stats(self, built_kg: TypeScriptKG) -> None:
        stats = built_kg.stats()
        assert stats["total_nodes"] > 0
        assert stats["total_edges"] > 0

    def test_class_nodes_present(self, built_kg: TypeScriptKG) -> None:
        stats = built_kg.stats()
        assert stats["node_counts"].get("class", 0) >= 2

    def test_function_nodes_present(self, built_kg: TypeScriptKG) -> None:
        stats = built_kg.stats()
        assert stats["node_counts"].get("function", 0) >= 3

    def test_interface_nodes_present(self, built_kg: TypeScriptKG) -> None:
        stats = built_kg.stats()
        assert stats["node_counts"].get("interface", 0) >= 2


class TestQuery:
    def test_query_returns_nodes(self, built_kg: TypeScriptKG) -> None:
        result = built_kg.query("authentication handler", k=5)
        assert result.returned_nodes > 0

    def test_query_finds_auth_handler(self, built_kg: TypeScriptKG) -> None:
        result = built_kg.query("authenticate request token", k=5)
        node_names = [n.get("name") for n in result.nodes]
        assert any("Auth" in (n or "") for n in node_names)


class TestPack:
    def test_pack_returns_snippets(self, built_kg: TypeScriptKG) -> None:
        pack = built_kg.pack("error handling", k=5)
        assert pack.returned_nodes > 0
        markdown = pack.to_markdown()
        assert "```" in markdown

    def test_pack_markdown_has_line_numbers(self, built_kg: TypeScriptKG) -> None:
        pack = built_kg.pack("validate URL", k=5)
        markdown = pack.to_markdown()
        # Line-numbered snippets contain the line number format "   N: "
        assert any(char.isdigit() for char in markdown)


class TestAnalyze:
    def test_analyze_returns_markdown(self, built_kg: TypeScriptKG) -> None:
        report = built_kg.analyze()
        assert "TypeScriptKG Repository Analysis" in report
        assert "Total Nodes" in report


class TestBuildVersusUpdate:
    """`build` wipes, `update` upserts — the distinction the two commands exist for.

    A deleted source file is the case that separates them. Its nodes are
    phantoms after an upsert: nothing in the new extraction mentions them, so
    an upsert has no reason to touch them. Only a wipe clears them.
    """

    def _kg(self, repo: Path, tmp_path: Path) -> TypeScriptKG:
        return TypeScriptKG(
            repo_root=repo,
            db_path=tmp_path / "graph.sqlite",
            vectors_path=tmp_path / "vectors.sqlite",
        )

    def test_update_keeps_nodes_from_a_deleted_file(self, tmp_repo: Path, tmp_path: Path) -> None:
        extra = tmp_repo / "src" / "doomed.ts"
        extra.write_text("export class Doomed { gone(): string { return 'x'; } }\n")

        kg = self._kg(tmp_repo, tmp_path)
        kg.build(wipe=True)
        before = kg.stats()["total_nodes"]

        extra.unlink()
        kg.build(wipe=False)

        assert kg.stats()["total_nodes"] == before, (
            "an upsert must not remove nodes for files that vanished"
        )

    def test_build_clears_nodes_from_a_deleted_file(self, tmp_repo: Path, tmp_path: Path) -> None:
        extra = tmp_repo / "src" / "doomed.ts"
        extra.write_text("export class Doomed { gone(): string { return 'x'; } }\n")

        kg = self._kg(tmp_repo, tmp_path)
        kg.build(wipe=True)
        before = kg.stats()["total_nodes"]

        extra.unlink()
        kg.build(wipe=True)

        assert kg.stats()["total_nodes"] < before, (
            "a full rebuild must drop nodes for files that vanished"
        )
