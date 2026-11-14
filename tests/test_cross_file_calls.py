"""
test_cross_file_calls.py -- CALLS edges that cross files or come from JSX.

A function called only from another module, or a React component used only
as ``<Component />``, used to have no CALLS edge into it and was reported as
an orphan. Extensionless imports of ``.tsx`` files also resolved to a
nonexistent ``.ts`` module.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rich.console import Console

from tscode_kg.analysis import TSCodeKGAnalyzer
from tscode_kg.extractor import _HAS_TREE_SITTER, TSCodeExtractor
from tscode_kg.kg import TypeScriptKG

pytestmark = pytest.mark.skipif(not _HAS_TREE_SITTER, reason="tree-sitter-typescript not installed")

FILES = {
    "src/util.ts": "export function helper(): number { return 1; }\n",
    "src/Badge.tsx": "export function Badge() { return <span>hi</span>; }\n",
    "src/Card.tsx": ("export default function Card() { return <div />; }\n"),
    "src/App.tsx": (
        "import { helper as h } from './util';\n"
        "import { Badge } from './Badge';\n"
        "import Card from './Card';\n"
        "export function App() {\n"
        "  const n = h();\n"
        "  return (<div><section><ul><li><p><span><em><b><i>\n"
        "    <Badge />\n"
        "  </i></b></em></span></p></li></ul></section><Card>{n}</Card></div>);\n"
        "}\n"
    ),
}


@pytest.fixture
def jsx_repo(tmp_path: Path) -> Path:
    for rel, text in FILES.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return tmp_path


def _edges(repo: Path, rel: str) -> set[tuple[str, str]]:
    return {
        (e.source_id, e.target_id)
        for e in TSCodeExtractor(repo).extract()
        if not hasattr(e, "node_id") and e.relation == rel
    }


def test_call_to_aliased_import_resolves(jsx_repo: Path) -> None:
    assert ("fn:src/App.tsx:App", "fn:src/util.ts:helper") in _edges(jsx_repo, "CALLS")


def test_jsx_element_is_a_call(jsx_repo: Path) -> None:
    calls = _edges(jsx_repo, "CALLS")
    assert ("fn:src/App.tsx:App", "fn:src/Badge.tsx:Badge") in calls
    assert ("fn:src/App.tsx:App", "fn:src/Card.tsx:Card") in calls


def test_lowercase_jsx_is_not_a_call(jsx_repo: Path) -> None:
    targets = {t for _, t in _edges(jsx_repo, "CALLS")}
    assert not any(t.endswith((":div", ":span")) for t in targets)


def test_extensionless_import_finds_tsx(jsx_repo: Path) -> None:
    assert ("mod:src/App.tsx", "mod:src/Badge.tsx") in _edges(jsx_repo, "IMPORTS")


def test_analyzer_reads_scope_from_config(jsx_repo: Path, tmp_path: Path) -> None:
    (jsx_repo / "pyproject.toml").write_text(
        '[tool.tscodekg]\ninclude = ["src"]\nexclude = ["tests"]\n'
    )
    kg = TypeScriptKG(
        repo_root=jsx_repo,
        db_path=tmp_path / "graph.sqlite",
        vectors_path=tmp_path / "vectors.sqlite",
    )
    try:
        analyzer = TSCodeKGAnalyzer(kg, console=Console(quiet=True))
        assert analyzer.include_dirs == {"src"}
        assert analyzer.exclude_dirs == {"tests"}
    finally:
        kg.close()
