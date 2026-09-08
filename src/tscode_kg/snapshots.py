"""
snapshots.py — Temporal Snapshots of TypeScriptKG Metrics

Thin layer over the shared ``kg_utils.snapshots`` module.  The shared module
provides the canonical ``Snapshot``, ``SnapshotManifest``, ``SnapshotManager``,
and ``PruneResult`` backed by free-form metric dicts; this module re-exports
those types and adds a ``SnapshotManager`` subclass whose entire body is the
``package_name = "tscode-kg"`` class attribute, so version auto-detection
resolves to this package.

Snapshots are keyed on a caller-supplied release tag or, absent one, a UTC
timestamp -- never a git tree hash, which is read before ``git add`` stages
the snapshot and so names a tree that is never committed. Stored in
``.tscodekg/snapshots/{key}.json`` with a ``manifest.json`` tracking all
snapshots and their metrics — the same layout PyCodeKG uses under
``.pycodekg/snapshots/``.

Usage
-----
>>> from tscode_kg.snapshots import SnapshotManager
>>> mgr = SnapshotManager(".tscodekg/snapshots")
>>> snapshot = mgr.capture(version="0.4.0", branch="main", key="0.4.0",
...                         subject="repo:tscode-kg", graph_stats_dict=stats)
>>> mgr.save_snapshot(snapshot)
>>> manifest = mgr.load_manifest()

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

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

    The whole class is one class attribute. It used to be an ``__init__``
    whose entire body forwarded to ``super()`` to change that one string.

    :param snapshots_dir: Directory holding snapshot JSON files and manifest.
    :param package_name: Package whose installed version stamps snapshots.
    :param db_path: Optional SQLite graph path for per-module node counts.
    """

    package_name = "tscode-kg"
