"""
cli/cmd_build.py — tscodekg build / update commands.

Builds the SQLite graph and sqlite-vec vector index from a TypeScript/JS repo.

Two commands, not one command with a flag, mirroring ``pycodekg``:

* ``build``  wipes existing data and rebuilds from scratch.
* ``update`` upserts changes without wiping.

The split matters because the two are different operations, not a switch on
one. A rebuild is correct after renames or deletions, where an upsert leaves
phantom nodes behind — the vector store upserts by node ID, so a renamed
symbol keeps its old entry forever. Making the safe operation the bare verb
means the surprising outcome has to be asked for by name.
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

console = Console()


def _build_options(fn):
    """Apply the option set shared by ``build`` and ``update``."""
    for option in reversed(
        [
            click.option(
                "--repo", default=".", show_default=True, help="Repository root directory."
            ),
            click.option(
                "--db",
                default=None,
                help="SQLite database path (default: <repo>/.tscodekg/graph.sqlite).",
            ),
            click.option(
                "--vectors",
                default=None,
                help="sqlite-vec store path (default: <repo>/.tscodekg/vectors.sqlite).",
            ),
            click.option(
                "--graph-only",
                is_flag=True,
                default=False,
                help="Build SQLite graph only; skip vector index.",
            ),
            click.option(
                "--index-only",
                is_flag=True,
                default=False,
                help="Build vector index only; graph must already exist.",
            ),
        ]
    ):
        fn = option(fn)
    return fn


def _run(
    *,
    repo: str,
    db: str | None,
    vectors: str | None,
    graph_only: bool,
    index_only: bool,
    wipe: bool,
) -> None:
    """Shared body for ``build`` and ``update``."""
    from tscode_kg.kg import TypeScriptKG  # pylint: disable=import-outside-toplevel

    repo_path = Path(repo).resolve()
    if not repo_path.is_dir():
        console.print(f"[red]Error:[/red] Repository not found: {repo_path}")
        raise SystemExit(1)

    kg = TypeScriptKG(
        repo_root=repo_path,
        db_path=db,
        vectors_path=vectors,
    )

    console.print(f"[bold]TypeScriptKG {'build' if wipe else 'update'}[/bold]")
    console.print(f"  repo    : {repo_path}")
    console.print(f"  db      : {kg.db_path}")
    console.print(f"  vectors : {kg.vectors_path}")
    console.print(f"  mode    : {'full rebuild (wipes)' if wipe else 'incremental upsert'}")
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


@click.command("build")
@_build_options
def build(
    repo: str,
    db: str | None,
    vectors: str | None,
    graph_only: bool,
    index_only: bool,
) -> None:
    """Build knowledge graph from scratch: wipes existing data, then extracts
    TypeScript/JS AST -> graph store -> vector index."""
    _run(
        repo=repo,
        db=db,
        vectors=vectors,
        graph_only=graph_only,
        index_only=index_only,
        wipe=True,
    )


@click.command("update")
@_build_options
def update(
    repo: str,
    db: str | None,
    vectors: str | None,
    graph_only: bool,
    index_only: bool,
) -> None:
    """Update knowledge graph incrementally: upserts changes without wiping
    existing data."""
    _run(
        repo=repo,
        db=db,
        vectors=vectors,
        graph_only=graph_only,
        index_only=index_only,
        wipe=False,
    )
