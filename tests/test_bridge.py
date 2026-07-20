"""Tests for module connectivity (bridge centrality) and framework detection."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from tscode_kg.bridge import compute_bridge_centrality
from tscode_kg.framework_detector import detect_framework_nodes

SCHEMA = """
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    qualname TEXT,
    module_path TEXT,
    lineno INTEGER,
    end_lineno INTEGER,
    docstring TEXT
);
CREATE TABLE edges (
    src TEXT NOT NULL,
    rel TEXT NOT NULL,
    dst TEXT NOT NULL,
    evidence TEXT,
    PRIMARY KEY (src, rel, dst)
);
"""


def _make_db(path: Path) -> Path:
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    # hub.ts calls into a.ts and b.ts; a.ts calls b.ts
    con.executemany(
        "INSERT INTO nodes (id, kind, name, qualname, module_path, lineno, end_lineno, docstring)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("mod:hub.ts", "module", "hub", "hub", "hub.ts", 1, 50, None),
            ("mod:a.ts", "module", "a", "a", "a.ts", 1, 50, None),
            ("mod:b.ts", "module", "b", "b", "b.ts", 1, 50, None),
            ("fn:hub.ts:run", "function", "run", "run", "hub.ts", 1, 10, None),
            ("fn:a.ts:fa", "function", "fa", "fa", "a.ts", 1, 10, None),
            ("fn:b.ts:fb", "function", "fb", "fb", "b.ts", 1, 10, None),
        ],
    )
    con.executemany(
        "INSERT INTO edges (src, rel, dst, evidence) VALUES (?, ?, ?, ?)",
        [
            ("fn:hub.ts:run", "CALLS", "fn:a.ts:fa", None),
            ("fn:hub.ts:run", "CALLS", "fn:b.ts:fb", None),
            ("fn:a.ts:fa", "CALLS", "fn:b.ts:fb", None),
            ("mod:hub.ts", "IMPORTS", "mod:a.ts", None),
            ("mod:hub.ts", "IMPORTS", "mod:b.ts", None),
        ],
    )
    con.commit()
    con.close()
    return path


def test_bridge_centrality_ranks_hub_first(tmp_path: Path) -> None:
    db = _make_db(tmp_path / "graph.sqlite")
    ranked = compute_bridge_centrality(top=10, db_path=str(db))
    assert ranked
    assert ranked[0][0] == "hub.ts"
    assert ranked[0][1] > 0


def test_bridge_centrality_persists_metric(tmp_path: Path) -> None:
    db = _make_db(tmp_path / "graph.sqlite")
    compute_bridge_centrality(top=10, db_path=str(db))
    con = sqlite3.connect(db)
    count = con.execute(
        "SELECT COUNT(*) FROM centrality_scores WHERE metric = 'module_connectivity'"
    ).fetchone()[0]
    con.close()
    assert count > 0


def test_detect_framework_nodes_returns_modules(tmp_path: Path) -> None:
    db = _make_db(tmp_path / "graph.sqlite")
    compute_bridge_centrality(top=10, db_path=str(db))
    nodes = detect_framework_nodes(limit=10, db_path=str(db))
    assert nodes
    labels = [label for _, _, label in nodes]
    assert "hub.ts" in labels
    # Only module paths — no function/method leakage
    for node_id, score, label in nodes:
        assert 0.0 <= score <= 1.0
        assert label.endswith(".ts")
