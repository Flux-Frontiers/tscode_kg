"""
cli/cmd_mcp.py -- ``tscodekg mcp``, the fleet's standard MCP command, from :mod:`kg_utils.mcp`:

    tscodekg mcp [--repo DIR] [--db FILE] [--vectors FILE] [--model NAME]
                 [--transport stdio|streamable-http] [--host H] [--port N]
                 [--manifest]

``cli/main.py`` registers it with ``add_mcp_command(cli, build_mcp_server)``.
Registering it imports neither ``mcp`` nor the server module, so every other
``tscodekg`` command starts as fast as before.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kg_utils.mcp import KGServer


def build_mcp_server(
    repo: Path, db: Path | None, vectors: Path | None, model: str | None
) -> KGServer:
    """Build the server only when ``tscodekg mcp`` runs.

    :param repo: Repository root, absolute.
    :param db: Graph database, absolute; ``None`` for the default.
    :param vectors: Vector store, absolute; ``None`` for the default.
    :param model: Embedding model; ``None`` for the default.
    :return: The server, with its graph not yet opened.
    """
    from tscode_kg.mcp_server import build_server  # noqa: PLC0415 -- see the module docstring

    return build_server(repo, db, vectors, model)
