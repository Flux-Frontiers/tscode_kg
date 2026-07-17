#!/usr/bin/env python3
"""
extractor.py — TypeScript/JavaScript AST extractor for TypeScriptKG.

Uses tree-sitter to parse .ts, .tsx, .js, and .jsx files and emit NodeSpec /
EdgeSpec objects for the KGModule build pipeline.

Node kinds:
  module      — every indexed source file
  class       — class declaration
  interface   — TypeScript interface
  type_alias  — TypeScript type alias
  enum        — TypeScript enum
  namespace   — TypeScript namespace / module declaration
  function    — module-level function (declaration or const arrow)
  method      — method / accessor within a class
  symbol      — unresolved import stub

Edge relations:
  CONTAINS    — module→class/function/interface…, class→method
  IMPORTS     — module→module (resolved from import paths)
  CALLS       — function/method→function (best-effort via call expressions)
  INHERITS    — class extends class
  IMPLEMENTS  — class implements interface
  EXTENDS     — interface extends interface

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from kg_utils.extractor import KGExtractor
from kg_utils.specs import EdgeSpec, NodeSpec

try:
    import tree_sitter_typescript as _tst
    from tree_sitter import Language, Parser

    _TS_LANGUAGE = Language(_tst.language_typescript())
    _TSX_LANGUAGE = Language(_tst.language_tsx())
    _HAS_TREE_SITTER = True
except Exception:  # noqa: BLE001
    _HAS_TREE_SITTER = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKIP_DIRS: frozenset[str] = frozenset(
    {
        "node_modules",
        ".git",
        "__pycache__",
        ".venv",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "coverage",
        ".nyc_output",
        ".turbo",
        ".cache",
        "out",
        ".output",
        ".pycodekg",
        ".dockg",
        ".agentkg",
        ".tscodekg",
        ".tscode_kg",
        "vendor",
        ".yarn",
        ".pnp",
        "storybook-static",
    }
)

TS_EXTENSIONS: frozenset[str] = frozenset(
    {".ts", ".tsx", ".js", ".jsx", ".mts", ".cts", ".mjs", ".cjs"}
)

_KIND_PREFIX: dict[str, str] = {
    "module": "mod",
    "class": "cls",
    "interface": "iface",
    "type_alias": "type",
    "enum": "enum",
    "namespace": "ns",
    "function": "fn",
    "method": "meth",
    "symbol": "sym",
}

# tree-sitter node types that declare a named scope
_CLASS_LIKE = frozenset({"class_declaration", "class"})
_INTERFACE_LIKE = frozenset({"interface_declaration"})
_TYPE_ALIAS = frozenset({"type_alias_declaration"})
_ENUM = frozenset({"enum_declaration"})
_NAMESPACE = frozenset({"module_declaration", "internal_module", "namespace_declaration"})
_METHOD_LIKE = frozenset(
    {"method_definition", "method_signature", "public_field_definition"}
)
_FUNCTION_LIKE = frozenset(
    {"function_declaration", "generator_function_declaration"}
)
_CALL_EXPR = frozenset({"call_expression", "new_expression"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_node_id(kind: str, rel_path: str, qualname: str = "") -> str:
    prefix = _KIND_PREFIX.get(kind, kind[:3])
    if qualname:
        return f"{prefix}:{rel_path}:{qualname}"
    return f"{prefix}:{rel_path}"


def _node_text(node: Any, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _child_text(node: Any, field: str, source: bytes) -> str:
    child = node.child_by_field_name(field)
    if child is None:
        return ""
    return _node_text(child, source)


def _extract_jsdoc(node: Any, source: bytes) -> str:
    """Look for the immediately-preceding /** ... */ comment.

    Handles two cases:
    1. ``node`` is a direct child of program/class_body — look at its siblings.
    2. ``node`` is wrapped in ``export_statement`` — look at the export's siblings.
    """
    # Resolve the "anchor" node whose preceding sibling should be the comment.
    # If the direct parent is export_statement, the comment sits before the export.
    anchor = node
    parent = node.parent
    if parent is not None and parent.type == "export_statement":
        anchor = parent
        parent = anchor.parent

    if parent is None:
        return ""

    children = list(parent.children)
    idx = next((i for i, c in enumerate(children) if c.id == anchor.id), -1)
    if idx <= 0:
        return ""
    prev = children[idx - 1]
    if prev.type != "comment":
        return ""
    text = _node_text(prev, source).strip()
    if not text.startswith("/**"):
        return ""
    inner = text[3:]
    if inner.endswith("*/"):
        inner = inner[:-2]
    lines = [re.sub(r"^\s*\*\s?", "", ln) for ln in inner.splitlines()]
    return " ".join(ln for ln in lines if ln.strip())


def _lineno(node: Any) -> int:
    """1-based start line."""
    return node.start_point[0] + 1


def _end_lineno(node: Any) -> int:
    """1-based end line."""
    return node.end_point[0] + 1


def _resolve_import_path(importing_file: str, raw_spec: str) -> str:
    """
    Best-effort resolution of a relative import specifier to a repo-relative path.

    Absolute/package imports become a ``sym:`` ID; relative imports are joined to
    the importing file's directory and normalised.
    """
    if not raw_spec.startswith("."):
        # Bare package import → symbol stub
        module_name = raw_spec.split("/")[0].lstrip("@")
        return f"sym:{module_name}"

    base = Path(importing_file).parent / raw_spec
    # Normalise without hitting the filesystem
    try:
        resolved = str(base).replace("\\", "/")
        # Strip leading ./
        resolved = re.sub(r"^\./", "", resolved)
    except Exception:  # noqa: BLE001
        resolved = raw_spec

    # If there's no extension, try .ts first (most common)
    if Path(resolved).suffix not in TS_EXTENSIONS:
        resolved = resolved + ".ts"
    return resolved


# ---------------------------------------------------------------------------
# Per-file walker
# ---------------------------------------------------------------------------


class _FileWalker:
    """Walk a single parsed tree and emit NodeSpec / EdgeSpec objects."""

    def __init__(self, rel_path: str, source: bytes, tree: Any) -> None:
        self.rel_path = rel_path
        self.source = source
        self.root = tree.root_node
        self._mod_id = _make_node_id("module", rel_path)
        self._emitted: list[NodeSpec | EdgeSpec] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def walk(self) -> list[NodeSpec | EdgeSpec]:
        self._emitted = []
        self._emit_module()
        self._walk_node(self.root, class_ctx=None)
        return self._emitted

    # ------------------------------------------------------------------
    # Module node
    # ------------------------------------------------------------------

    def _emit_module(self) -> None:
        doc = self._module_jsdoc()
        self._emitted.append(
            NodeSpec(
                node_id=self._mod_id,
                kind="module",
                name=Path(self.rel_path).name,
                qualname=self.rel_path,
                source_path=self.rel_path,
                lineno=1,
                end_lineno=self.root.end_point[0] + 1,
                docstring=doc,
            )
        )

    def _module_jsdoc(self) -> str:
        """Return the first top-level /** comment if any."""
        for child in self.root.children:
            if child.type == "comment":
                text = _node_text(child, self.source).strip()
                if text.startswith("/**"):
                    inner = text[3:]
                    if inner.endswith("*/"):
                        inner = inner[:-2]
                    lines = [re.sub(r"^\s*\*\s?", "", ln) for ln in inner.splitlines()]
                    return " ".join(ln for ln in lines if ln.strip())
                break
            if child.type not in ("comment", "hash_bang_line"):
                break
        return ""

    # ------------------------------------------------------------------
    # Recursive walker
    # ------------------------------------------------------------------

    def _walk_node(self, node: Any, class_ctx: str | None) -> None:
        t = node.type

        if t == "import_statement":
            self._handle_import(node)
            return

        if t in _CLASS_LIKE:
            self._handle_class(node)
            return

        if t in _INTERFACE_LIKE:
            self._handle_interface(node)
            return

        if t in _TYPE_ALIAS:
            self._handle_type_alias(node)
            return

        if t in _ENUM:
            self._handle_enum(node)
            return

        if t in _NAMESPACE:
            self._handle_namespace(node)
            return

        if t in _FUNCTION_LIKE and class_ctx is None:
            self._handle_function(node)
            return

        if t == "export_statement":
            self._handle_export(node, class_ctx)
            return

        if t == "lexical_declaration" and class_ctx is None:
            self._handle_lexical_declaration(node)
            return

        # Recurse into anything else (but not into class bodies — handled above)
        for child in node.children:
            self._walk_node(child, class_ctx)

    # ------------------------------------------------------------------
    # Import handling
    # ------------------------------------------------------------------

    def _handle_import(self, node: Any) -> None:
        """Emit IMPORTS edge from this module to the imported module."""
        source_node = node.child_by_field_name("source")
        if source_node is None:
            return
        raw = _node_text(source_node, self.source).strip("'\"` \t")
        if not raw:
            return
        target = _resolve_import_path(self.rel_path, raw)
        if target.startswith("sym:"):
            target_id = target
        else:
            target_id = _make_node_id("module", target)
        self._emitted.append(
            EdgeSpec(source_id=self._mod_id, target_id=target_id, relation="IMPORTS")
        )

    # ------------------------------------------------------------------
    # Class handling
    # ------------------------------------------------------------------

    def _handle_class(self, node: Any) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = _node_text(name_node, self.source)
        node_id = _make_node_id("class", self.rel_path, name)
        doc = _extract_jsdoc(node, self.source)

        self._emitted.append(
            NodeSpec(
                node_id=node_id,
                kind="class",
                name=name,
                qualname=name,
                source_path=self.rel_path,
                lineno=_lineno(node),
                end_lineno=_end_lineno(node),
                docstring=doc,
            )
        )
        self._emitted.append(
            EdgeSpec(source_id=self._mod_id, target_id=node_id, relation="CONTAINS")
        )

        # Heritage: extends / implements (class_heritage is a direct child, not a named field)
        heritage = next((c for c in node.children if c.type == "class_heritage"), None)
        if heritage is not None:
            self._handle_class_heritage(heritage, node_id)

        # Body: methods
        body = node.child_by_field_name("body")
        if body is not None:
            for child in body.children:
                if child.type in _METHOD_LIKE:
                    self._handle_method(child, class_name=name, class_id=node_id)

    def _handle_class_heritage(self, heritage_node: Any, class_id: str) -> None:
        for child in heritage_node.children:
            if child.type == "extends_clause":
                for c in child.children:
                    if c.type in ("identifier", "member_expression"):
                        base_name = _node_text(c, self.source).split(".")[0]
                        target_id = _make_node_id("class", self.rel_path, base_name)
                        self._emitted.append(
                            EdgeSpec(
                                source_id=class_id,
                                target_id=target_id,
                                relation="INHERITS",
                            )
                        )
                        break
            elif child.type == "implements_clause":
                for c in child.children:
                    if c.type in ("identifier", "generic_type", "type_identifier"):
                        iface_name = _node_text(c, self.source).split("<")[0].strip()
                        target_id = _make_node_id("interface", self.rel_path, iface_name)
                        self._emitted.append(
                            EdgeSpec(
                                source_id=class_id,
                                target_id=target_id,
                                relation="IMPLEMENTS",
                            )
                        )

    # ------------------------------------------------------------------
    # Method handling
    # ------------------------------------------------------------------

    def _handle_method(self, node: Any, class_name: str, class_id: str) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = _node_text(name_node, self.source)
        qualname = f"{class_name}.{name}"
        node_id = _make_node_id("method", self.rel_path, qualname)
        doc = _extract_jsdoc(node, self.source)

        self._emitted.append(
            NodeSpec(
                node_id=node_id,
                kind="method",
                name=name,
                qualname=qualname,
                source_path=self.rel_path,
                lineno=_lineno(node),
                end_lineno=_end_lineno(node),
                docstring=doc,
            )
        )
        self._emitted.append(
            EdgeSpec(source_id=class_id, target_id=node_id, relation="CONTAINS")
        )

        # CALLS edges from method body
        body = node.child_by_field_name("body") or node.child_by_field_name("value")
        if body is not None:
            for call_name in self._collect_calls(body):
                call_target = _make_node_id("function", self.rel_path, call_name)
                self._emitted.append(
                    EdgeSpec(source_id=node_id, target_id=call_target, relation="CALLS")
                )

    # ------------------------------------------------------------------
    # Interface handling
    # ------------------------------------------------------------------

    def _handle_interface(self, node: Any) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = _node_text(name_node, self.source)
        node_id = _make_node_id("interface", self.rel_path, name)
        doc = _extract_jsdoc(node, self.source)

        self._emitted.append(
            NodeSpec(
                node_id=node_id,
                kind="interface",
                name=name,
                qualname=name,
                source_path=self.rel_path,
                lineno=_lineno(node),
                end_lineno=_end_lineno(node),
                docstring=doc,
            )
        )
        self._emitted.append(
            EdgeSpec(source_id=self._mod_id, target_id=node_id, relation="CONTAINS")
        )

        # interface extends clause — tree-sitter uses extends_type_clause as direct child
        extends_clause = next(
            (c for c in node.children if c.type == "extends_type_clause"), None
        )
        if extends_clause is not None:
            for c in extends_clause.children:
                if c.type in ("identifier", "type_identifier"):
                    base_name = _node_text(c, self.source)
                    target_id = _make_node_id("interface", self.rel_path, base_name)
                    self._emitted.append(
                        EdgeSpec(source_id=node_id, target_id=target_id, relation="EXTENDS")
                    )

    # ------------------------------------------------------------------
    # Type alias handling
    # ------------------------------------------------------------------

    def _handle_type_alias(self, node: Any) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = _node_text(name_node, self.source)
        node_id = _make_node_id("type_alias", self.rel_path, name)
        doc = _extract_jsdoc(node, self.source)

        self._emitted.append(
            NodeSpec(
                node_id=node_id,
                kind="type_alias",
                name=name,
                qualname=name,
                source_path=self.rel_path,
                lineno=_lineno(node),
                end_lineno=_end_lineno(node),
                docstring=doc,
            )
        )
        self._emitted.append(
            EdgeSpec(source_id=self._mod_id, target_id=node_id, relation="CONTAINS")
        )

    # ------------------------------------------------------------------
    # Enum handling
    # ------------------------------------------------------------------

    def _handle_enum(self, node: Any) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = _node_text(name_node, self.source)
        node_id = _make_node_id("enum", self.rel_path, name)
        doc = _extract_jsdoc(node, self.source)

        # Collect member names as metadata
        body = node.child_by_field_name("body")
        members: list[str] = []
        if body is not None:
            for child in body.children:
                if child.type == "enum_assignment":
                    mname = child.child_by_field_name("name")
                    if mname:
                        members.append(_node_text(mname, self.source))
                elif child.type in ("identifier", "string"):
                    members.append(_node_text(child, self.source).strip("'\""))

        self._emitted.append(
            NodeSpec(
                node_id=node_id,
                kind="enum",
                name=name,
                qualname=name,
                source_path=self.rel_path,
                lineno=_lineno(node),
                end_lineno=_end_lineno(node),
                docstring=doc or (f"Enum with members: {', '.join(members)}" if members else ""),
                metadata={"members": members},
            )
        )
        self._emitted.append(
            EdgeSpec(source_id=self._mod_id, target_id=node_id, relation="CONTAINS")
        )

    # ------------------------------------------------------------------
    # Namespace handling
    # ------------------------------------------------------------------

    def _handle_namespace(self, node: Any) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = _node_text(name_node, self.source)
        node_id = _make_node_id("namespace", self.rel_path, name)
        doc = _extract_jsdoc(node, self.source)

        self._emitted.append(
            NodeSpec(
                node_id=node_id,
                kind="namespace",
                name=name,
                qualname=name,
                source_path=self.rel_path,
                lineno=_lineno(node),
                end_lineno=_end_lineno(node),
                docstring=doc,
            )
        )
        self._emitted.append(
            EdgeSpec(source_id=self._mod_id, target_id=node_id, relation="CONTAINS")
        )

    # ------------------------------------------------------------------
    # Function handling
    # ------------------------------------------------------------------

    def _handle_function(self, node: Any) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = _node_text(name_node, self.source)
        node_id = _make_node_id("function", self.rel_path, name)
        doc = _extract_jsdoc(node, self.source)

        self._emitted.append(
            NodeSpec(
                node_id=node_id,
                kind="function",
                name=name,
                qualname=name,
                source_path=self.rel_path,
                lineno=_lineno(node),
                end_lineno=_end_lineno(node),
                docstring=doc,
            )
        )
        self._emitted.append(
            EdgeSpec(source_id=self._mod_id, target_id=node_id, relation="CONTAINS")
        )

        body = node.child_by_field_name("body")
        if body is not None:
            for call_name in self._collect_calls(body):
                call_target = _make_node_id("function", self.rel_path, call_name)
                self._emitted.append(
                    EdgeSpec(source_id=node_id, target_id=call_target, relation="CALLS")
                )

    # ------------------------------------------------------------------
    # Export statement: unwrap and delegate
    # ------------------------------------------------------------------

    def _handle_export(self, node: Any, class_ctx: str | None) -> None:
        for child in node.children:
            if child.type in _CLASS_LIKE:
                self._handle_class(child)
            elif child.type in _INTERFACE_LIKE:
                self._handle_interface(child)
            elif child.type in _TYPE_ALIAS:
                self._handle_type_alias(child)
            elif child.type in _ENUM:
                self._handle_enum(child)
            elif child.type in _NAMESPACE:
                self._handle_namespace(child)
            elif child.type in _FUNCTION_LIKE and class_ctx is None:
                self._handle_function(child)
            elif child.type == "lexical_declaration" and class_ctx is None:
                self._handle_lexical_declaration(child)

    # ------------------------------------------------------------------
    # Lexical declarations: const/let fn = () => {}
    # ------------------------------------------------------------------

    def _handle_lexical_declaration(self, node: Any) -> None:
        """Handle ``const fn = () => {}`` style function declarations."""
        for declarator in node.children:
            if declarator.type != "variable_declarator":
                continue
            name_node = declarator.child_by_field_name("name")
            value_node = declarator.child_by_field_name("value")
            if name_node is None or value_node is None:
                continue
            if value_node.type not in (
                "arrow_function",
                "function",
                "function_expression",
                "generator_function",
            ):
                continue

            name = _node_text(name_node, self.source)
            if not re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", name):
                continue

            node_id = _make_node_id("function", self.rel_path, name)
            doc = _extract_jsdoc(node, self.source)

            self._emitted.append(
                NodeSpec(
                    node_id=node_id,
                    kind="function",
                    name=name,
                    qualname=name,
                    source_path=self.rel_path,
                    lineno=_lineno(node),
                    end_lineno=_end_lineno(value_node),
                    docstring=doc,
                )
            )
            self._emitted.append(
                EdgeSpec(source_id=self._mod_id, target_id=node_id, relation="CONTAINS")
            )

            body = value_node.child_by_field_name("body")
            if body is not None:
                for call_name in self._collect_calls(body):
                    call_target = _make_node_id("function", self.rel_path, call_name)
                    self._emitted.append(
                        EdgeSpec(source_id=node_id, target_id=call_target, relation="CALLS")
                    )

    # ------------------------------------------------------------------
    # Call expression collector
    # ------------------------------------------------------------------

    def _collect_calls(self, body_node: Any, depth: int = 0) -> list[str]:
        """Recursively collect directly-called function names (simple identifiers only)."""
        if depth > 10:
            return []
        calls: list[str] = []
        for child in body_node.children:
            if child.type in _CALL_EXPR:
                fn_node = child.child_by_field_name("function")
                if fn_node is not None and fn_node.type == "identifier":
                    name = _node_text(fn_node, self.source)
                    if re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", name):
                        calls.append(name)
            calls.extend(self._collect_calls(child, depth + 1))
        return calls


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def _find_ts_files(
    repo_root: Path,
    include: set[str],
    exclude: set[str],
) -> list[Path]:
    """Walk repo_root and return all TypeScript/JavaScript source files."""
    all_excludes = SKIP_DIRS | exclude
    result: list[Path] = []

    def _walk(directory: Path, depth: int) -> None:
        try:
            entries = sorted(directory.iterdir())
        except PermissionError:
            return
        for entry in entries:
            if entry.name.startswith(".") and entry.name not in {"."}:
                # Keep .ts/.tsx files even in hidden dirs (unlikely), skip hidden dirs
                if entry.is_dir():
                    continue
            if entry.is_dir():
                if entry.name in all_excludes:
                    continue
                if depth == 0 and include and entry.name not in include:
                    continue
                _walk(entry, depth + 1)
            elif entry.is_file() and entry.suffix in TS_EXTENSIONS:
                result.append(entry)

    _walk(repo_root, depth=0)
    return result


# ---------------------------------------------------------------------------
# TSCodeExtractor
# ---------------------------------------------------------------------------


class TSCodeExtractor(KGExtractor):
    """
    KGExtractor backed by tree-sitter TypeScript / JavaScript AST parsing.

    Yields :class:`NodeSpec` and :class:`EdgeSpec` objects for every .ts,
    .tsx, .js, and .jsx file found under ``repo_path``.

    :param repo_path: Absolute path to the TypeScript/JavaScript repository.
    :param include: Top-level directory names to include (empty = all).
    :param exclude: Directory names to exclude at every depth.
    :param config: Optional domain config dict.
    """

    def __init__(
        self,
        repo_path: Path,
        *,
        include: set[str] | None = None,
        exclude: set[str] | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(repo_path, config)
        self._include: set[str] = include or set()
        self._exclude: set[str] = exclude or set()

    # ------------------------------------------------------------------
    # KGExtractor protocol
    # ------------------------------------------------------------------

    def node_kinds(self) -> list[str]:
        return [
            "module",
            "class",
            "interface",
            "type_alias",
            "enum",
            "namespace",
            "function",
            "method",
            "symbol",
        ]

    def edge_kinds(self) -> list[str]:
        return [
            "CONTAINS",
            "IMPORTS",
            "CALLS",
            "INHERITS",
            "IMPLEMENTS",
            "EXTENDS",
        ]

    def meaningful_node_kinds(self) -> list[str]:
        """Exclude symbol stubs from LanceDB indexing and coverage metrics."""
        return [
            "module",
            "class",
            "interface",
            "type_alias",
            "enum",
            "namespace",
            "function",
            "method",
        ]

    def extract(self) -> Iterator[NodeSpec | EdgeSpec]:
        if not _HAS_TREE_SITTER:
            raise RuntimeError(
                "tree-sitter and tree-sitter-typescript are required. "
                "Install with: pip install tree-sitter tree-sitter-typescript"
            )

        files = _find_ts_files(self.repo_path, self._include, self._exclude)
        for abs_path in files:
            try:
                rel_path = str(abs_path.relative_to(self.repo_path)).replace("\\", "/")
                source = abs_path.read_bytes()
                # Choose language based on extension
                lang = _TSX_LANGUAGE if abs_path.suffix in {".tsx", ".jsx"} else _TS_LANGUAGE
                parser = Parser(lang)
                tree = parser.parse(source)
                walker = _FileWalker(rel_path, source, tree)
                yield from walker.walk()
            except Exception:  # noqa: BLE001
                continue
