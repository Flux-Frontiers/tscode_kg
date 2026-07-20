"""
cli/cmd_query.py — tscodekg query / pack commands.
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.command("query")
@click.argument("q")
@click.option("--repo", default=".", show_default=True, help="Repository root.")
@click.option("-k", default=8, show_default=True, help="Semantic seed count.")
@click.option("--hop", default=1, show_default=True, help="Graph expansion hops.")
@click.option("--max-nodes", default=25, show_default=True, help="Maximum nodes returned.")
@click.option(
    "--rerank",
    default="hybrid",
    show_default=True,
    type=click.Choice(["hybrid", "semantic", "legacy"]),
    help="Reranking strategy.",
)
def query(q: str, repo: str, k: int, hop: int, max_nodes: int, rerank: str) -> None:
    """Query the TypeScript/JS knowledge graph."""
    from tscode_kg.kg import TypeScriptKG  # pylint: disable=import-outside-toplevel

    kg = TypeScriptKG(repo_root=Path(repo).resolve())
    result = kg.query(q, k=k, hop=hop, max_nodes=max_nodes, rerank_mode=rerank)
    result.print_summary()


@click.command("pack")
@click.argument("q")
@click.option("--repo", default=".", show_default=True, help="Repository root.")
@click.option("-k", default=8, show_default=True, help="Semantic seed count.")
@click.option("--hop", default=1, show_default=True, help="Graph expansion hops.")
@click.option("--max-nodes", default=15, show_default=True, help="Maximum nodes in pack.")
@click.option("--max-lines", default=60, show_default=True, help="Maximum lines per snippet.")
@click.option(
    "--rerank",
    default="hybrid",
    show_default=True,
    type=click.Choice(["hybrid", "semantic", "legacy"]),
    help="Reranking strategy.",
)
@click.option("--out", default=None, help="Output file path (.md or .json).")
def pack(
    q: str,
    repo: str,
    k: int,
    hop: int,
    max_nodes: int,
    max_lines: int,
    rerank: str,
    out: str | None,
) -> None:
    """Pack source snippets from the TypeScript/JS knowledge graph."""
    from tscode_kg.kg import TypeScriptKG  # pylint: disable=import-outside-toplevel

    kg = TypeScriptKG(repo_root=Path(repo).resolve())
    pack_result = kg.pack(
        q, k=k, hop=hop, max_nodes=max_nodes, max_lines=max_lines, rerank_mode=rerank
    )

    if out:
        fmt = "json" if out.endswith(".json") else "md"
        pack_result.save(out, fmt=fmt)
        console.print(f"[green]Saved to {out}[/green]")
    else:
        console.print(pack_result.to_markdown())
