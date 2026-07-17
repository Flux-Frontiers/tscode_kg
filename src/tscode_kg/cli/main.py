"""
cli/main.py — TypeScriptKG CLI entry point.

Usage::

    tscodekg build --repo /path/to/ts-repo
    tscodekg query "authentication middleware"
    tscodekg pack "error handling" --hop 2
    tscodekg mcp --repo /path/to/ts-repo
"""

from __future__ import annotations

import click

from tscode_kg.cli.cmd_build import build
from tscode_kg.cli.cmd_mcp import mcp_cmd
from tscode_kg.cli.cmd_query import pack, query


@click.group()
@click.version_option(package_name="tscode-kg")
def cli() -> None:
    """TypeScriptKG — knowledge graph for TypeScript/JavaScript codebases."""


cli.add_command(build)
cli.add_command(query)
cli.add_command(pack)
cli.add_command(mcp_cmd, name="mcp")
