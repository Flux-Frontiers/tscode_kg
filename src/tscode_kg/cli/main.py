"""
cli/main.py — TypeScriptKG CLI entry point.

Usage::

    tscodekg init --repo /path/to/ts-repo
    tscodekg build --repo /path/to/ts-repo
    tscodekg query "authentication middleware"
    tscodekg pack "error handling" --hop 2
    tscodekg analyze /path/to/ts-repo
    tscodekg snapshot save --repo /path/to/ts-repo
    tscodekg install-hooks --repo /path/to/ts-repo
    tscodekg mcp --repo /path/to/ts-repo
"""

from __future__ import annotations

import click

from tscode_kg.cli.cmd_analyze import analyze
from tscode_kg.cli.cmd_build import build
from tscode_kg.cli.cmd_hooks import install_hooks
from tscode_kg.cli.cmd_init import init
from tscode_kg.cli.cmd_mcp import mcp_cmd
from tscode_kg.cli.cmd_model import download_model
from tscode_kg.cli.cmd_query import pack, query
from tscode_kg.cli.cmd_snapshot import snapshot


@click.group()
@click.version_option(package_name="tscode-kg")
def cli() -> None:
    """TypeScriptKG — knowledge graph for TypeScript/JavaScript codebases."""


cli.add_command(init)
cli.add_command(build)
cli.add_command(query)
cli.add_command(pack)
cli.add_command(analyze)
cli.add_command(snapshot)
cli.add_command(install_hooks)
cli.add_command(download_model)
cli.add_command(mcp_cmd, name="mcp")
