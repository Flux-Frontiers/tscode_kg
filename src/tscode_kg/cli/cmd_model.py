"""
cli/cmd_model.py — tscodekg download-model command.

  download-model — download and cache the sentence-transformer model for offline use
"""

from __future__ import annotations

import click


@click.command("download-model")
@click.option(
    "--model",
    default=None,
    help="SentenceTransformer model name to download (default: shared kg_utils default).",
)
@click.option(
    "--force",
    is_flag=True,
    help="Re-download even if a local copy already exists.",
)
def download_model(model: str | None, force: bool) -> None:
    """Download and cache the embedding model for offline use.

    The model is saved to the shared kg_utils model cache
    (``./.kgcache/models/<model>/`` by default, overridable via the
    ``KGRAG_MODEL_DIR`` environment variable).  Once cached,
    ``tscodekg build`` and ``tscodekg query`` use this local copy without
    any network access.
    """
    from kg_utils.semantic import (  # pylint: disable=import-outside-toplevel
        DEFAULT_MODEL,
        _local_model_path,
    )
    from sentence_transformers import (  # pylint: disable=import-outside-toplevel
        SentenceTransformer,
    )

    model = model or DEFAULT_MODEL
    local_path = _local_model_path(model)

    if local_path.exists() and not force:
        click.echo(f"Model already cached at {local_path}")
        click.echo("Use --force to re-download.")
        return

    click.echo(f"Downloading model '{model}'...")
    st_model = SentenceTransformer(model)
    local_path.mkdir(parents=True, exist_ok=True)
    st_model.save(str(local_path))
    click.echo(f"OK: model saved to {local_path}")
