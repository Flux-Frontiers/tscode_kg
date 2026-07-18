"""
test_explain.py

Tests for the shared ``render_explain`` presenter that backs both the CLI
``tscodekg explain`` command and the MCP ``explain`` tool.  These tests guard
the kind-aware role labels adapted from PyCodeKG to the TS/JS vocabulary.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from tscode_kg.explain import render_explain
from tscode_kg.extractor import _HAS_TREE_SITTER
from tscode_kg.kg import TypeScriptKG

pytestmark = pytest.mark.skipif(not _HAS_TREE_SITTER, reason="tree-sitter-typescript not installed")


def _make_kg(tmp_path: Path, source: str) -> TypeScriptKG:
    repo = tmp_path / "repo"
    src_file = repo / "src" / "mod.ts"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text(textwrap.dedent(source))
    kg = TypeScriptKG(
        repo_root=repo,
        db_path=tmp_path / "graph.sqlite",
        vectors_path=tmp_path / "vectors.sqlite",
    )
    kg.build_graph(wipe=True)
    return kg


def _node_id_by_name(kg: TypeScriptKG, kind: str, name: str) -> str:
    return next(n["id"] for n in kg.store.query_nodes(kinds=[kind]) if n["name"] == name)


def test_render_explain_unknown_node_returns_not_found(tmp_path):
    kg = _make_kg(tmp_path, "export function foo(): void {}\n")
    md = render_explain(kg, "fn:does/not/exist.ts:bogus")
    assert "Node Not Found" in md
    assert "bogus" in md
    kg.close()


def test_render_explain_orphan_function_zero_callers(tmp_path):
    kg = _make_kg(tmp_path, "export function lonely(): void {}\n")
    fn_id = _node_id_by_name(kg, "function", "lonely")
    md = render_explain(kg, fn_id)
    assert "Orphaned" in md
    kg.close()


def test_render_explain_interface_type_level_label(tmp_path):
    src = """
        export interface Shape {
          area(): number;
        }
    """
    kg = _make_kg(tmp_path, src)
    iface_id = _node_id_by_name(kg, "interface", "Shape")
    md = render_explain(kg, iface_id)
    assert "Interface: `Shape`" in md
    assert "Type-level declaration" in md
    kg.close()


def test_render_explain_uses_snippets_hint(tmp_path):
    """Footer call-to-action is parameterized for CLI vs MCP."""
    kg = _make_kg(tmp_path, "export function foo(): void {}\n")
    fn_id = _node_id_by_name(kg, "function", "foo")

    md_mcp = render_explain(kg, fn_id, snippets_hint="pack_snippets()")
    md_cli = render_explain(kg, fn_id, snippets_hint="tscodekg pack")

    assert "pack_snippets()" in md_mcp
    assert "tscodekg pack" not in md_mcp
    assert "tscodekg pack" in md_cli
    assert "pack_snippets()" not in md_cli
    kg.close()


def test_render_explain_has_expected_sections(tmp_path):
    """Smoke test: a documented function with a caller renders the standard sections."""
    src = """
        /** This is a documented function. */
        export function documented(): number {
          return 1;
        }

        export function caller(): number {
          return documented();
        }
    """
    kg = _make_kg(tmp_path, src)
    fn_id = _node_id_by_name(kg, "function", "documented")
    md = render_explain(kg, fn_id)
    assert "## Metadata" in md
    assert "## Documentation" in md
    assert "This is a documented function." in md
    assert "## Called By (Callers)" in md
    assert "## Role in Codebase" in md
    kg.close()
