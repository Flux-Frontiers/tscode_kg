"""
test_snapshots.py — unit tests for the TypeScriptKG snapshot layer.

Exercises the tscode_kg.snapshots.SnapshotManager (thin subclass of the
kg_utils base) end-to-end on a temporary directory: capture, save, list,
show, diff. No embedding model or git repository required — branch, tree
hash and key are passed explicitly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

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
            key="v0.1.0",
            subject="repo:tscode-kg",
        )
        saved = mgr.save_snapshot(snap)
        assert saved is not None and saved.exists()
        assert snap.key == "v0.1.0"
        assert snap.subject == "repo:tscode-kg"
        assert snap.tree_hash == "a" * 40
        assert snap.metrics["total_nodes"] == 20
        assert snap.metrics["critical_issues"] == 1

    def test_package_version_autodetect_targets_tscode_kg(self, tmp_path: Path) -> None:
        mgr = SnapshotManager(tmp_path / "snapshots")
        assert mgr.package_name == "tscode-kg"

    def test_list_and_load(self, tmp_path: Path) -> None:
        mgr = SnapshotManager(tmp_path / "snapshots")
        for i, (nodes, tree, key) in enumerate(
            [(20, "a" * 40, "v0.1.0"), (25, "b" * 40, "v0.1.1")]
        ):
            snap = mgr.capture(
                version=f"0.1.{i}",
                branch="develop",
                graph_stats_dict=_fake_stats(nodes, nodes + 10, 0.5),
                tree_hash=tree,
                key=key,
            )
            mgr.save_snapshot(snap)

        entries = mgr.list_snapshots()
        assert len(entries) == 2
        # Most recent first
        assert entries[0]["key"] == "v0.1.1"
        assert entries[0]["metrics"]["total_nodes"] == 25

        loaded = mgr.load_snapshot("v0.1.0")
        assert loaded is not None
        assert loaded.metrics["total_nodes"] == 20

    def test_deltas(self, tmp_path: Path) -> None:
        mgr = SnapshotManager(tmp_path / "snapshots")
        first = mgr.capture(
            version="0.1.0",
            branch="develop",
            graph_stats_dict=_fake_stats(20, 30, 0.5),
            tree_hash="a" * 40,
            key="v0.1.0",
        )
        mgr.save_snapshot(first)

        second = mgr.capture(
            version="0.1.1",
            branch="develop",
            graph_stats_dict=_fake_stats(26, 33, 0.6),
            tree_hash="b" * 40,
            key="v0.1.1",
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
        for i, (nodes, tree, key) in enumerate(
            [(20, "a" * 40, "v0.1.0"), (26, "b" * 40, "v0.1.1")]
        ):
            snap = mgr.capture(
                version=f"0.1.{i}",
                branch="develop",
                graph_stats_dict=_fake_stats(nodes, nodes + 10, 0.5),
                tree_hash=tree,
                key=key,
            )
            mgr.save_snapshot(snap)

        diff = mgr.diff_snapshots("v0.1.0", "v0.1.1")
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
            key="v0.1.0",
        )
        with pytest.raises(ValueError, match="degenerate"):
            mgr.save_snapshot(snap)


class TestKeyScheme:
    """A snapshot is keyed on the supplied tag, not the tree hash."""

    def test_capture_without_a_key_does_not_use_the_tree_hash(self, tmp_path: Path) -> None:
        mgr = SnapshotManager(tmp_path / "snapshots")
        snap = mgr.capture(
            version="0.1.0",
            branch="develop",
            graph_stats_dict=_fake_stats(20, 30, 0.5),
            tree_hash="d" * 40,
        )
        assert snap.key != "d" * 40
        assert snap.tree_hash == "d" * 40

    def test_save_snapshot_persists_key_subject_and_tool(self, tmp_path: Path) -> None:
        import json

        mgr = SnapshotManager(tmp_path / "snapshots")
        snap = mgr.capture(
            version="0.4.0",
            branch="main",
            graph_stats_dict=_fake_stats(20, 30, 0.5),
            tree_hash="e" * 40,
            key="v0.4.0",
            subject="repo:tscode-kg",
        )
        saved = mgr.save_snapshot(snap)
        assert saved is not None and saved.name == "v0.4.0.json"

        on_disk = json.loads(saved.read_text(encoding="utf-8"))
        assert on_disk["key"] == "v0.4.0"
        assert on_disk["subject"] == "repo:tscode-kg"
        assert on_disk["tree_hash"] == "e" * 40
        assert on_disk["tool"] == "tscode-kg"
        assert on_disk["tool_version"]


def test_package_name_comes_from_the_class_attribute(tmp_path: Path) -> None:
    """The manager is now one class attribute; this is the whole contract.

    Against kgmodule-utils < 0.20.0 the base has no package_name class
    attribute, so every snapshot's tool field would read "kg-utils".
    """
    assert SnapshotManager.package_name == "tscode-kg"
    assert SnapshotManager(tmp_path / "snapshots").package_name == "tscode-kg"


class TestRepoVersion:
    """With no VERSION given, a snapshot records the measured repo's version."""

    def test_root_package_json(self, tmp_path: Path) -> None:
        from tscode_kg.cli.cmd_snapshot import repo_version

        (tmp_path / "package.json").write_text('{"name": "web", "version": "2.3.4"}')
        (tmp_path / "CITATION.cff").write_text('version: "9.9.9"\n')
        assert repo_version(tmp_path) == "2.3.4"

    def test_citation_when_no_root_package_json(self, tmp_path: Path) -> None:
        from tscode_kg.cli.cmd_snapshot import repo_version

        (tmp_path / "CITATION.cff").write_text('cff-version: "1.2.0"\nversion: "1.24.0"\n')
        assert repo_version(tmp_path) == "1.24.0"

    def test_package_json_without_version_falls_through(self, tmp_path: Path) -> None:
        from tscode_kg.cli.cmd_snapshot import repo_version

        (tmp_path / "package.json").write_text('{"private": true}')
        (tmp_path / "CITATION.cff").write_text("version: 1.0.0\n")
        assert repo_version(tmp_path) == "1.0.0"

    def test_unreadable_package_json_falls_through(self, tmp_path: Path) -> None:
        from tscode_kg.cli.cmd_snapshot import repo_version

        (tmp_path / "package.json").write_text("{not json")
        assert repo_version(tmp_path) is None

    def test_neither(self, tmp_path: Path) -> None:
        from tscode_kg.cli.cmd_snapshot import repo_version

        assert repo_version(tmp_path) is None

    def test_capture_records_repo_version_and_keeps_timestamp_key(self, tmp_repo: Path) -> None:
        pytest.importorskip("tree_sitter_typescript")
        import tscode_kg
        from tscode_kg.cli.cmd_snapshot import capture_snapshot
        from tscode_kg.kg import TypeScriptKG

        (tmp_repo / "CITATION.cff").write_text('version: "1.24.0"\n')
        db = tmp_repo / ".tscodekg" / "graph.sqlite"
        kg = TypeScriptKG(repo_root=tmp_repo, db_path=db)
        kg.build_graph(wipe=True)
        kg.close()

        capture_snapshot(
            version=None,
            repo=str(tmp_repo),
            db=None,
            snapshots_dir=None,
            branch="main",
            tree_hash="a" * 40,
        )

        snap = SnapshotManager(tmp_repo / ".tscodekg" / "snapshots").load_manifest().snapshots[0]
        assert snap["version"] == "1.24.0"
        assert snap["tool_version"] == tscode_kg.__version__
        assert snap["key"] != "1.24.0"
