"""
snapshots.py — Temporal Snapshots of TypeScriptKG Metrics

Thin layer over the shared ``kg_utils.snapshots`` module.  The shared module
provides the canonical ``Snapshot``, ``SnapshotManifest``, ``SnapshotManager``,
and ``PruneResult`` backed by free-form metric dicts; this module re-exports
those types and adds a ``SnapshotManager`` subclass that defaults
``package_name`` to ``"tscode-kg"`` so version auto-detection resolves to this
package.

Snapshots are stored in ``.tscodekg/snapshots/{tree_hash}.json`` with a
``manifest.json`` tracking all snapshots and their metrics — the same layout
PyCodeKG uses under ``.pycodekg/snapshots/``.

Usage
-----
>>> from tscode_kg.snapshots import SnapshotManager
>>> mgr = SnapshotManager(".tscodekg/snapshots")
>>> snapshot = mgr.capture(version="0.1.0", branch="develop", graph_stats_dict=stats)
>>> mgr.save_snapshot(snapshot)
>>> manifest = mgr.load_manifest()

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

from pathlib import Path

from kg_utils.snapshots import (
    PruneResult,  # noqa: F401  re-exported
    Snapshot,  # noqa: F401  re-exported
    SnapshotManifest,  # noqa: F401  re-exported
)
from kg_utils.snapshots import SnapshotManager as _BaseSnapshotManager

__all__ = [
    "Snapshot",
    "SnapshotManifest",
    "SnapshotManager",
    "PruneResult",
]


class SnapshotManager(_BaseSnapshotManager):
    """Snapshot manager bound to the ``tscode-kg`` package.

    Identical to :class:`kg_utils.snapshots.SnapshotManager` except that
    version auto-detection resolves against the installed ``tscode-kg``
    package instead of ``kg-utils``.

    :param snapshots_dir: Directory holding snapshot JSON files and manifest.
    :param package_name: Package whose installed version stamps snapshots.
    :param db_path: Optional SQLite graph path for per-module node counts.
    """

    def __init__(
        self,
        snapshots_dir: Path | str,
        *,
        package_name: str = "tscode-kg",
        db_path: Path | str | None = None,
    ) -> None:
        super().__init__(snapshots_dir, package_name=package_name, db_path=db_path)
