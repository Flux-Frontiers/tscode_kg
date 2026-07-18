"""
test_snapshots.py — unit tests for the TypeScriptKG snapshot layer.

Exercises the tscode_kg.snapshots.SnapshotManager (thin subclass of the
kg_utils base) end-to-end on a temporary directory: capture, save, list,
show, diff. No embedding model or git repository required — branch and
tree hash are passed explicitly.
"""

from __future__ import annotations

from pathlib import Path

from tscode_kg.snapshots import SnapshotManager


def _fake_stats(nodes: int, edges: int, coverage: float) -> dict:
    return {
        "total_nodes": nodes,
        "meaningful_nodes": nodes - 2,
        "total_edges": edges,
        "docstring_coverage": coverage,
        "node_counts": {"function": nodes - 5, "class": 3, "module": 2},
        "edge_counts": {"CALLS": edges - 4, "CONTAINS": 4},
    }


class TestSnapshotRoundTrip:
    def test_capture_and_save(self, tmp_path: Path) -> None:
        mgr = SnapshotManager(tmp_path / "snapshots")
        snap = mgr.capture(
            version="0.1.0",
            branch="develop",
            graph_stats_dict=_fake_stats(20, 30, 0.5),
            critical_issues=1,
            complexity_median=2.0,
            tree_hash="a" * 40,
        )
        saved = mgr.save_snapshot(snap)
        assert saved is not None and saved.exists()
        assert snap.key == "a" * 40
        assert snap.metrics["total_nodes"] == 20
        assert snap.metrics["critical_issues"] == 1

    def test_package_version_autodetect_targets_tscode_kg(self, tmp_path: Path) -> None:
        mgr = SnapshotManager(tmp_path / "snapshots")
        assert mgr.package_name == "tscode-kg"

    def test_list_and_load(self, tmp_path: Path) -> None:
        mgr = SnapshotManager(tmp_path / "snapshots")
        for i, (nodes, tree) in enumerate([(20, "a" * 40), (25, "b" * 40)]):
            snap = mgr.capture(
                version=f"0.1.{i}",
                branch="develop",
                graph_stats_dict=_fake_stats(nodes, nodes + 10, 0.5),
                tree_hash=tree,
            )
            mgr.save_snapshot(snap)

        entries = mgr.list_snapshots()
        assert len(entries) == 2
        # Most recent first
        assert entries[0]["key"] == "b" * 40
        assert entries[0]["metrics"]["total_nodes"] == 25

        loaded = mgr.load_snapshot("a" * 40)
        assert loaded is not None
        assert loaded.metrics["total_nodes"] == 20

    def test_deltas(self, tmp_path: Path) -> None:
        mgr = SnapshotManager(tmp_path / "snapshots")
        first = mgr.capture(
            version="0.1.0",
            branch="develop",
            graph_stats_dict=_fake_stats(20, 30, 0.5),
            tree_hash="a" * 40,
        )
        mgr.save_snapshot(first)

        second = mgr.capture(
            version="0.1.1",
            branch="develop",
            graph_stats_dict=_fake_stats(26, 33, 0.6),
            tree_hash="b" * 40,
        )
        # vs_baseline is computed at capture time against the oldest snapshot
        assert second.vs_baseline is not None
        assert second.vs_baseline["nodes"] == 6
        assert second.vs_baseline["edges"] == 3

        # vs_previous deltas are filled in lazily by list_snapshots
        mgr.save_snapshot(second)
        entries = mgr.list_snapshots()
        assert entries[0]["deltas"]["vs_previous"]["nodes"] == 6

    def test_diff_snapshots(self, tmp_path: Path) -> None:
        mgr = SnapshotManager(tmp_path / "snapshots")
        for i, (nodes, tree) in enumerate([(20, "a" * 40), (26, "b" * 40)]):
            snap = mgr.capture(
                version=f"0.1.{i}",
                branch="develop",
                graph_stats_dict=_fake_stats(nodes, nodes + 10, 0.5),
                tree_hash=tree,
            )
            mgr.save_snapshot(snap)

        diff = mgr.diff_snapshots("a" * 40, "b" * 40)
        assert "error" not in diff
        assert diff["delta"]["nodes"] == 6
        assert diff["node_counts_delta"]["function"] == 6

    def test_save_rejects_empty_graph(self, tmp_path: Path) -> None:
        import pytest

        mgr = SnapshotManager(tmp_path / "snapshots")
        snap = mgr.capture(
            version="0.1.0",
            branch="develop",
            graph_stats_dict={"total_nodes": 0, "total_edges": 0},
            tree_hash="c" * 40,
        )
        with pytest.raises(ValueError, match="degenerate"):
            mgr.save_snapshot(snap)
