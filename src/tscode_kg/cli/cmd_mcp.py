"""
cli/cmd_mcp.py — tscodekg mcp command: launch the MCP server.
"""

from __future__ import annotations

import click


@click.command("mcp")
@click.option("--repo", default=".", show_default=True, help="Repository root.")
@click.option(
    "--db",
    default=".tscodekg/graph.sqlite",
    show_default=True,
    help="SQLite database path.",
)
@click.option(
    "--lancedb",
    default=".tscodekg/lancedb",
    show_default=True,
    help="LanceDB directory.",
)
@click.option(
    "--transport",
    default="stdio",
    show_default=True,
    type=click.Choice(["stdio", "sse"]),
    help="MCP transport.",
)
def mcp_cmd(repo: str, db: str, lancedb: str, transport: str) -> None:
    """Launch the TypeScriptKG MCP server."""
    from tscode_kg.mcp_server import main  # pylint: disable=import-outside-toplevel

    main(["--repo", repo, "--db", db, "--lancedb", lancedb, "--transport", transport])
