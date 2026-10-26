"""
test_mcp_server.py

The TypeScriptKG MCP server on the fleet's shared base, ``kg_utils.mcp``.

Import-level regression tests first: the server's import of ``mcp`` breaks at
import time, not call time, when an incompatible ``mcp`` release is installed
(mcp 2.0 removed ``mcp.server.fastmcp``), and only for people who installed
from PyPI. Ported from pycode_kg's ``tests/test_mcp_server.py``.

Then the surface step 2 of kgrag_priv's MCP centralization plan promises: the
five canonical tools first, under the same names as every fleet server, then
TypeScriptKG's own; ``query`` and ``pack`` keep TypeScriptKG's richer search;
the manifest answers without a graph; ``tscodekg``'s other commands do not
pay for importing ``mcp``; and a real stdio subprocess serves.

Last, manifest parity with PyCodeKG, the reference port: the canonical tools'
names, order and shared parameter schemas must match its. PyCodeKG is not a
dependency of this repo, so its canonical manifest is a checked-in fixture,
``tests/fixtures/pycodekg_canonical_manifest.json``. Regenerate it after a
pycode_kg MCP change with a Python that has kgmodule-utils 0.29+ and ``mcp``
(this repo's venv works) and pycode_kg's source on the path::

    PYTHONPATH=/path/to/pycode_kg/src .venv/bin/python -c "
    import json
    from kg_utils.mcp import CANONICAL_TOOLS, manifest
    from pycode_kg.mcp_server import build_server
    m = manifest(build_server('.'))
    out = {'name': m['name'], 'kind': m['kind'], 'canonical': m['canonical'],
           'tools': [t for t in m['tools'] if t['name'] in CANONICAL_TOOLS]}
    print(json.dumps(out, indent=2))
    " > tests/fixtures/pycodekg_canonical_manifest.json

The checked-in copy was generated from pycode_kg ``78d4a83``
(``feat/mcp-server-base``).
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import anyio
import pytest
from click.testing import CliRunner
from kg_utils.mcp import CANONICAL_TOOLS, manifest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import tscode_kg
from tscode_kg.cli.main import cli
from tscode_kg.extractor import _HAS_TREE_SITTER
from tscode_kg.kg import TypeScriptKG
from tscode_kg.mcp_server import EXTRA_TOOLS, build_server

_SRC = str(Path(tscode_kg.__file__).resolve().parents[1])
_PYCODEKG_MANIFEST = Path(__file__).parent / "fixtures" / "pycodekg_canonical_manifest.json"

needs_tree_sitter = pytest.mark.skipif(
    not _HAS_TREE_SITTER, reason="tree-sitter-typescript not installed"
)


def _script(repo: Path, *args: str) -> list[str]:
    """Run ``tscodekg-mcp``'s entry point the way the console script does."""
    return [
        sys.executable,
        "-c",
        "from tscode_kg.mcp_server import main; main()",
        "--repo",
        str(repo),
        *args,
    ]


def _manifest(tmp_path: Path) -> dict:
    return manifest(build_server(tmp_path))


# ---------------------------------------------------------------------------
# Import level
# ---------------------------------------------------------------------------


def test_server_module_imports():
    """The module must import cleanly against the installed mcp release."""
    importlib.import_module("tscode_kg.mcp_server")


def test_fastmcp_import_path_exists():
    """``mcp.server.fastmcp`` must exist -- mcp 2.0 removed it.

    Asserted directly so the failure names the actual incompatibility rather
    than surfacing as an opaque ImportError from kg_utils.mcp.
    """
    importlib.import_module("mcp.server.fastmcp")


def test_entry_point_target_exists():
    """``tscodekg-mcp`` resolves to tscode_kg.mcp_server:main."""
    server = importlib.import_module("tscode_kg.mcp_server")
    assert callable(server.main)


# ---------------------------------------------------------------------------
# The tool surface
# ---------------------------------------------------------------------------


def test_canonical_tools_come_first_then_tscodekgs_own(tmp_path):
    names = [t["name"] for t in _manifest(tmp_path)["tools"]]
    assert names == [*CANONICAL_TOOLS, *(fn.__name__ for fn in EXTRA_TOOLS)]
    # The count docs/MCP.md and the README state.
    assert len(names) == 20


def test_the_manifest_names_the_server_and_its_kind(tmp_path):
    m = _manifest(tmp_path)
    assert (m["name"], m["kind"], m["version"]) == ("tscodekg", "code", tscode_kg.__version__)
    assert m["canonical"] == list(CANONICAL_TOOLS)


def test_query_and_pack_keep_tscodekgs_richer_search(tmp_path):
    """Swapping in the plain canonical pair would have regressed ranking."""
    tools = {t["name"]: t["input_schema"]["properties"] for t in _manifest(tmp_path)["tools"]}
    for name in ("query", "pack"):
        props = tools[name]
        assert props["rerank_mode"]["default"] == "hybrid", name
        assert props["max_per_module"]["default"] == 3, name
        assert "rerank_semantic_weight" in props and "rerank_lexical_weight" in props, name
    assert "context" in tools["pack"] and "max_lines" in tools["pack"]


def test_instructions_carry_the_workflows_and_every_tool(tmp_path):
    server = build_server(tmp_path)
    text = server.instructions or ""
    assert "Recommended workflows" in text
    for name in (*CANONICAL_TOOLS, *(fn.__name__ for fn in EXTRA_TOOLS)):
        assert f"- `{name}`:" in text, name


# ---------------------------------------------------------------------------
# Manifest parity with PyCodeKG
# ---------------------------------------------------------------------------


def test_canonical_tools_match_pycodekgs_names_and_order(tmp_path):
    ref = json.loads(_PYCODEKG_MANIFEST.read_text(encoding="utf-8"))
    ours = _manifest(tmp_path)
    assert ours["canonical"] == ref["canonical"] == list(CANONICAL_TOOLS)
    assert [t["name"] for t in ours["tools"][:5]] == [t["name"] for t in ref["tools"]]


def test_canonical_tools_share_pycodekgs_parameter_schemas(tmp_path):
    """Every parameter both servers take is spelled, typed and defaulted alike.

    The SDK's own tools (``stats``, ``get_node``, ``neighbors``) must match
    whole. ``query`` and ``pack`` are each module's richer version, so each
    may add parameters the other lacks; the ones they share must agree.
    """
    ref = {
        t["name"]: t for t in json.loads(_PYCODEKG_MANIFEST.read_text(encoding="utf-8"))["tools"]
    }
    ours = {t["name"]: t for t in _manifest(tmp_path)["tools"][:5]}
    for name in ("stats", "get_node", "neighbors"):
        assert ours[name] == ref[name], name
    for name in ("query", "pack"):
        mine, theirs = ours[name]["input_schema"], ref[name]["input_schema"]
        shared = mine["properties"].keys() & theirs["properties"].keys()
        assert {"q", "k", "hop", "max_nodes", "rels"} <= shared, name
        for param in sorted(shared):
            assert mine["properties"][param] == theirs["properties"][param], (name, param)
        assert mine.get("required", []) == theirs.get("required", []), name


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------


def test_manifest_answers_without_a_graph_and_creates_nothing(tmp_path):
    result = CliRunner().invoke(cli, ["mcp", "--repo", str(tmp_path), "--manifest"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["canonical"] == list(CANONICAL_TOOLS)
    assert not (tmp_path / ".tscodekg").exists()


def test_both_entry_points_are_the_same_command(tmp_path):
    via_cli = CliRunner().invoke(cli, ["mcp", "--repo", str(tmp_path), "--manifest"]).output
    via_script = subprocess.run(
        _script(tmp_path, "--manifest"), check=True, capture_output=True, text=True
    ).stdout
    assert json.loads(via_cli) == json.loads(via_script)


def test_sse_is_no_longer_offered(tmp_path):
    result = CliRunner().invoke(cli, ["mcp", "--repo", str(tmp_path), "--transport", "sse"])
    assert result.exit_code == 2


def test_other_commands_do_not_import_mcp():
    """Registering ``tscodekg mcp`` must not slow every other command."""
    out = subprocess.run(
        [sys.executable, "-c", "import sys, tscode_kg.cli.main; print('mcp' in sys.modules)"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert out == "False"


# ---------------------------------------------------------------------------
# A real stdio subprocess
# ---------------------------------------------------------------------------


@needs_tree_sitter
def test_stdio_subprocess_initializes_and_serves(tmp_repo):
    kg = TypeScriptKG(tmp_repo)
    kg.build_graph(wipe=True)
    kg.close()
    params = StdioServerParameters(
        command=sys.executable,
        args=_script(tmp_repo)[1:],
        env={**os.environ, "PYTHONPATH": _SRC},
    )

    async def session():
        with open(tmp_repo / "stderr.log", "w", encoding="utf-8") as errlog:
            async with stdio_client(params, errlog=errlog) as (read, write):
                async with ClientSession(read, write) as client:
                    init = await client.initialize()
                    tools = await client.list_tools()
                    stats = await client.call_tool("stats", {})
                    found = await client.call_tool("find_node", {"name": "AuthHandler"})
                    return init, tools, stats, found

    init, tools, stats, found = anyio.run(session)
    assert (init.serverInfo.name, init.serverInfo.version) == ("tscodekg", tscode_kg.__version__)
    assert [t.name for t in tools.tools][:5] == list(CANONICAL_TOOLS)
    assert not stats.isError and stats.structuredContent["nodes"]["total"] > 0
    assert stats.structuredContent["kind"] == "code"
    assert not found.isError and "AuthHandler" in found.content[0].text


# ---------------------------------------------------------------------------
# With the real model: query and pack through MCP
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.integration
@needs_tree_sitter
def test_query_and_pack_with_the_real_model(tmp_repo):
    from mcp.shared.memory import create_connected_server_and_client_session

    kg = TypeScriptKG(tmp_repo)
    kg.build(wipe=True)
    kg.close()

    async def session():
        async with create_connected_server_and_client_session(build_server(tmp_repo)) as client:
            return (
                await client.call_tool("query", {"q": "authenticate request token", "k": 3}),
                await client.call_tool("pack", {"q": "validate a url", "k": 3}),
            )

    found, packed = anyio.run(session)
    assert not found.isError and found.structuredContent["returned_nodes"] >= 1
    assert found.structuredContent["nodes"][0]["relevance"]["mode"] == "hybrid"
    assert not packed.isError and "validateUrl" in packed.content[0].text
