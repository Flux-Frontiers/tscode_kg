"""Tests for Structural Importance Ranking (SIR)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from tscode_kg.centrality import StructuralImportanceRanker, aggregate_module_scores

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
    con.executemany(
        "INSERT INTO nodes (id, kind, name, qualname, module_path, lineno, end_lineno, docstring)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("fn:a.ts:f1", "function", "f1", "f1", "a.ts", 1, 2, None),
            ("fn:b.ts:f2", "function", "f2", "f2", "b.ts", 1, 2, None),
            ("fn:core.ts:core", "function", "core", "core", "core.ts", 1, 2, None),
            ("sym:core", "symbol", "core", "core", "b.ts", 1, 1, None),
            ("mod:core.ts", "module", "core", "core", "core.ts", 1, 100, None),
        ],
    )
    con.executemany(
        "INSERT INTO edges (src, rel, dst, evidence) VALUES (?, ?, ?, ?)",
        [
            ("fn:a.ts:f1", "CALLS", "fn:core.ts:core", None),
            ("fn:b.ts:f2", "CALLS", "sym:core", None),
            ("sym:core", "RESOLVES_TO", "fn:core.ts:core", None),
            ("mod:core.ts", "CONTAINS", "fn:core.ts:core", None),
        ],
    )
    con.commit()
    con.close()
    return path


def test_sir_resolves_symbol_edges(tmp_path: Path) -> None:
    db = _make_db(tmp_path / "graph.sqlite")
    ranker = StructuralImportanceRanker(db)
    records = ranker.compute()
    top = records[0]
    assert top.node_id == "fn:core.ts:core"
    assert top.inbound_count >= 2


def test_module_aggregation(tmp_path: Path) -> None:
    db = _make_db(tmp_path / "graph.sqlite")
    ranker = StructuralImportanceRanker(db)
    records = ranker.compute()
    modules = aggregate_module_scores(records)
    assert modules[0]["module_path"] == "core.ts"


def test_write_scores_persists_metric(tmp_path: Path) -> None:
    db = _make_db(tmp_path / "graph.sqlite")
    ranker = StructuralImportanceRanker(db)
    records = ranker.compute()
    written = ranker.write_scores(records, metric="sir_pagerank")
    assert written == len(records)

    con = sqlite3.connect(db)
    rows = con.execute(
        "SELECT COUNT(*) FROM centrality_scores WHERE metric = 'sir_pagerank'"
    ).fetchone()
    con.close()
    assert rows[0] == len(records)
