"""
test_mcp_cold_start.py

Regression tests for MCP tools called first in a fresh server session.

``KGModule.store`` is a lazy property: ``_store`` stays ``None`` until the
property is first read. ``list_nodes`` and ``find_node`` reached for the
private ``_store`` field instead, so as the first call of a session they
answered "No database store available". Ported from pycode_kg, which fixed
the same bug.
"""

from __future__ import annotations

import json
from pathlib import Path

import anyio
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from tscode_kg.extractor import _HAS_TREE_SITTER
from tscode_kg.kg import TypeScriptKG
from tscode_kg.mcp_server import build_server

pytestmark = pytest.mark.skipif(not _HAS_TREE_SITTER, reason="tree-sitter-typescript not installed")


def _first_call(repo: Path, tool: str, args: dict) -> list:
    """Make *tool* the first call of a fresh server session over a built graph.

    The server opens its own handle when the session starts, so the store is
    as cold as it is in a newly launched server process.
    """
    kg = TypeScriptKG(repo)
    kg.build_graph(wipe=True)
    kg.close()

    async def session():
        async with create_connected_server_and_client_session(build_server(repo)) as client:
            return await client.call_tool(tool, args)

    result = anyio.run(session)
    assert not result.isError, result.content
    return json.loads(result.content[0].text)


def test_list_nodes_works_on_cold_session(tmp_repo):
    payload = _first_call(tmp_repo, "list_nodes", {"kind": "class"})

    assert not (isinstance(payload, dict) and "error" in payload), payload
    assert any(n["name"] == "AuthHandler" for n in payload)


def test_find_node_works_on_cold_session(tmp_repo):
    payload = _first_call(tmp_repo, "find_node", {"name": "validateUrl"})

    assert not (isinstance(payload, dict) and "error" in payload), payload
    assert any(n["name"] == "validateUrl" for n in payload)


def test_store_property_initialises_on_first_access(tmp_repo):
    kg = TypeScriptKG(tmp_repo)
    assert kg._store is None  # noqa: SLF001
    assert kg.store is not None
    assert kg._store is not None  # noqa: SLF001
    kg.close()
