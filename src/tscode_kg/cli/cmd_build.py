"""
cli/cmd_build.py — tscodekg build command.

Builds the SQLite graph and LanceDB vector index from a TypeScript/JS repo.
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.command("build")
@click.option("--repo", default=".", show_default=True, help="Repository root directory.")
@click.option(
    "--db",
    default=None,
    help="SQLite database path (default: <repo>/.tscodekg/graph.sqlite).",
)
@click.option(
    "--lancedb",
    default=None,
    help="LanceDB directory (default: <repo>/.tscodekg/lancedb).",
)
@click.option("--wipe", is_flag=True, default=False, help="Clear existing data before building.")
@click.option(
    "--graph-only",
    is_flag=True,
    default=False,
    help="Build SQLite graph only; skip vector index.",
)
@click.option(
    "--index-only",
    is_flag=True,
    default=False,
    help="Build vector index only; graph must already exist.",
)
def build(
    repo: str,
    db: str | None,
    lancedb: str | None,
    wipe: bool,
    graph_only: bool,
    index_only: bool,
) -> None:
    """Build the TypeScript/JS knowledge graph for a repository."""
    from tscode_kg.kg import TypeScriptKG  # pylint: disable=import-outside-toplevel

    repo_path = Path(repo).resolve()
    if not repo_path.is_dir():
        console.print(f"[red]Error:[/red] Repository not found: {repo_path}")
        raise SystemExit(1)

    kg = TypeScriptKG(
        repo_root=repo_path,
        db_path=db,
        lancedb_dir=lancedb,
    )

    console.print(f"[bold]TypeScriptKG build[/bold]")
    console.print(f"  repo    : {repo_path}")
    console.print(f"  db      : {kg.db_path}")
    console.print(f"  lancedb : {kg.lancedb_dir}")
    console.print(f"  wipe    : {wipe}")
    console.print()

    try:
        if index_only:
            console.print("[cyan]Building vector index...[/cyan]")
            stats = kg.build_index(wipe=wipe)
        elif graph_only:
            console.print("[cyan]Building SQLite graph...[/cyan]")
            stats = kg.build_graph(wipe=wipe)
        else:
            console.print("[cyan]Building graph + vector index...[/cyan]")
            stats = kg.build(wipe=wipe)

        console.print("[green]Done.[/green]")
        console.print(str(stats))
    except Exception as exc:  # pylint: disable=broad-except
        console.print(f"[red]Build failed:[/red] {exc}")
        raise SystemExit(1) from exc
