"""
test_extractor.py — unit tests for TSCodeExtractor.

Tests AST extraction from the sample TypeScript fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tscode_kg.extractor import _HAS_TREE_SITTER, TSCodeExtractor

pytestmark = pytest.mark.skipif(not _HAS_TREE_SITTER, reason="tree-sitter-typescript not installed")

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _extract(tmp_repo: Path) -> tuple[list, list]:
    extractor = TSCodeExtractor(tmp_repo)
    nodes, edges = [], []
    for item in extractor.extract():
        if hasattr(item, "node_id"):
            nodes.append(item)
        else:
            edges.append(item)
    return nodes, edges


def _by_kind(nodes: list, kind: str) -> list:
    return [n for n in nodes if n.kind == kind]


def _by_name(nodes: list, name: str) -> list:
    return [n for n in nodes if n.name == name]


def _edges_by_rel(edges: list, rel: str) -> list:
    return [e for e in edges if e.relation == rel]


class TestModuleNode:
    def test_module_node_emitted(self, tmp_repo: Path) -> None:
        nodes, _ = _extract(tmp_repo)
        mods = _by_kind(nodes, "module")
        assert len(mods) == 1
        assert mods[0].source_path == "src/sample.ts"

    def test_module_node_id(self, tmp_repo: Path) -> None:
        nodes, _ = _extract(tmp_repo)
        mod = _by_kind(nodes, "module")[0]
        assert mod.node_id == "mod:src/sample.ts"

    def test_module_jsdoc(self, tmp_repo: Path) -> None:
        nodes, _ = _extract(tmp_repo)
        mod = _by_kind(nodes, "module")[0]
        assert "sample.ts" in mod.docstring.lower() or "fixture" in mod.docstring.lower()


class TestClassNodes:
    def test_base_handler_emitted(self, tmp_repo: Path) -> None:
        nodes, _ = _extract(tmp_repo)
        classes = _by_kind(nodes, "class")
        names = [n.name for n in classes]
        assert "BaseHandler" in names
        assert "AuthHandler" in names

    def test_class_line_numbers(self, tmp_repo: Path) -> None:
        nodes, _ = _extract(tmp_repo)
        base = next(n for n in nodes if n.name == "BaseHandler")
        assert base.lineno is not None and base.lineno > 0
        assert base.end_lineno is not None and base.end_lineno > base.lineno

    def test_class_jsdoc(self, tmp_repo: Path) -> None:
        nodes, _ = _extract(tmp_repo)
        base = next(n for n in nodes if n.name == "BaseHandler")
        assert "handler" in base.docstring.lower()


class TestInterfaceNodes:
    def test_interfaces_emitted(self, tmp_repo: Path) -> None:
        nodes, _ = _extract(tmp_repo)
        ifaces = _by_kind(nodes, "interface")
        names = [n.name for n in ifaces]
        assert "HandlerOptions" in names
        assert "AuthHandlerOptions" in names

    def test_interface_jsdoc(self, tmp_repo: Path) -> None:
        nodes, _ = _extract(tmp_repo)
        iface = next(n for n in nodes if n.name == "HandlerOptions")
        assert iface.docstring != ""


class TestTypeAliasNode:
    def test_type_alias_emitted(self, tmp_repo: Path) -> None:
        nodes, _ = _extract(tmp_repo)
        types = _by_kind(nodes, "type_alias")
        assert any(n.name == "StringMap" for n in types)


class TestEnumNode:
    def test_enum_emitted(self, tmp_repo: Path) -> None:
        nodes, _ = _extract(tmp_repo)
        enums = _by_kind(nodes, "enum")
        assert any(n.name == "HttpStatus" for n in enums)

    def test_enum_jsdoc(self, tmp_repo: Path) -> None:
        nodes, _ = _extract(tmp_repo)
        enum = next(n for n in nodes if n.name == "HttpStatus")
        assert enum.docstring != ""


class TestFunctionNodes:
    def test_functions_emitted(self, tmp_repo: Path) -> None:
        nodes, _ = _extract(tmp_repo)
        fns = _by_kind(nodes, "function")
        names = [n.name for n in fns]
        assert "validateUrl" in names
        assert "fetchData" in names
        assert "identity" in names

    def test_arrow_function_emitted(self, tmp_repo: Path) -> None:
        nodes, _ = _extract(tmp_repo)
        fns = _by_kind(nodes, "function")
        names = [n.name for n in fns]
        assert "buildUrl" in names

    def test_function_jsdoc(self, tmp_repo: Path) -> None:
        nodes, _ = _extract(tmp_repo)
        fn = next(n for n in nodes if n.name == "validateUrl")
        assert fn.docstring != ""


class TestMethodNodes:
    def test_methods_emitted(self, tmp_repo: Path) -> None:
        nodes, _ = _extract(tmp_repo)
        methods = _by_kind(nodes, "method")
        names = [n.name for n in methods]
        assert "execute" in names
        assert "refresh" in names

    def test_method_qualname(self, tmp_repo: Path) -> None:
        nodes, _ = _extract(tmp_repo)
        execute = next(n for n in nodes if n.name == "execute")
        assert execute.qualname == "AuthHandler.execute"


class TestEdges:
    def test_contains_edges(self, tmp_repo: Path) -> None:
        _, edges = _extract(tmp_repo)
        contains = _edges_by_rel(edges, "CONTAINS")
        assert len(contains) > 0

    def test_imports_edge(self, tmp_repo: Path) -> None:
        _, edges = _extract(tmp_repo)
        imports = _edges_by_rel(edges, "IMPORTS")
        assert len(imports) > 0
        # "events" and "path" are external packages → sym: stubs
        targets = [e.target_id for e in imports]
        assert any("sym:" in t for t in targets)

    def test_inherits_edge(self, tmp_repo: Path) -> None:
        _, edges = _extract(tmp_repo)
        inherits = _edges_by_rel(edges, "INHERITS")
        assert len(inherits) > 0
        # AuthHandler extends BaseHandler
        src_ids = [e.source_id for e in inherits]
        assert any("AuthHandler" in s for s in src_ids)

    def test_implements_edge(self, tmp_repo: Path) -> None:
        _, edges = _extract(tmp_repo)
        implements = _edges_by_rel(edges, "IMPLEMENTS")
        assert len(implements) > 0

    def test_extends_edge_on_interface(self, tmp_repo: Path) -> None:
        _, edges = _extract(tmp_repo)
        extends = _edges_by_rel(edges, "EXTENDS")
        # AuthHandlerOptions extends HandlerOptions
        assert len(extends) > 0

    def test_calls_edges(self, tmp_repo: Path) -> None:
        _, edges = _extract(tmp_repo)
        calls = _edges_by_rel(edges, "CALLS")
        assert len(calls) > 0
        # execute() calls validateUrl and fetchData
        src_ids = [e.source_id for e in calls]
        assert any("execute" in s for s in src_ids)
