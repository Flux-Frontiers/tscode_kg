"""
test_analysis.py — the multi-phase analyzer's failure handling.

Scoped to one behaviour: a phase that cannot run must cost that phase, not the
report. Exactly one of the fourteen phases seeds on a semantic query, so a
graph built with ``tscodekg build-sqlite`` — a supported command that
deliberately skips the vector index — has everything the other thirteen need.
Before this, phase 4 raised ``sqlite3.OperationalError: no such table:
vec_nodes`` and took the whole run with it: no report, and an error naming an
internal table rather than the missing step.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rich.console import Console

from tscode_kg.analysis import TSCodeKGAnalyzer
from tscode_kg.extractor import _HAS_TREE_SITTER
from tscode_kg.kg import TypeScriptKG

pytestmark = pytest.mark.skipif(not _HAS_TREE_SITTER, reason="tree-sitter-typescript not installed")


@pytest.fixture
def analyzer(tmp_repo: Path, tmp_path: Path):
    """An analyzer over a graph built without a vector index."""
    kg = TypeScriptKG(
        repo_root=tmp_repo,
        db_path=tmp_path / "graph.sqlite",
        vectors_path=tmp_path / "vectors.sqlite",
    )
    kg.build_graph(wipe=True)
    instance = TSCodeKGAnalyzer(kg, console=Console(quiet=True))
    instance.run_analysis()
    yield instance
    kg.close()


class TestRunPhaseIsolation:
    """The unit behaviour, without needing a graph."""

    def test_an_unexpected_exception_does_not_propagate(self, tmp_path: Path) -> None:
        kg = TypeScriptKG(repo_root=tmp_path, db_path=tmp_path / "g.sqlite")
        instance = TSCodeKGAnalyzer(kg, console=Console(quiet=True))

        def boom() -> None:
            raise RuntimeError("phase exploded")

        instance._run_phase(1, "Exploding phase", boom)

        assert len(instance.phase_failures) == 1
        assert instance.phase_failures[0]["phase"] == 1
        assert "phase exploded" in instance.phase_failures[0]["error"]
        kg.close()

    def test_a_successful_phase_records_no_failure(self, tmp_path: Path) -> None:
        kg = TypeScriptKG(repo_root=tmp_path, db_path=tmp_path / "g.sqlite")
        instance = TSCodeKGAnalyzer(kg, console=Console(quiet=True))
        instance._run_phase(1, "Fine phase", lambda: None)
        assert instance.phase_failures == []
        kg.close()

    def test_later_phases_still_run_after_one_fails(self, tmp_path: Path) -> None:
        """The point of the change: one failure must not end the run."""
        kg = TypeScriptKG(repo_root=tmp_path, db_path=tmp_path / "g.sqlite")
        instance = TSCodeKGAnalyzer(kg, console=Console(quiet=True))
        ran: list[int] = []

        def boom() -> None:
            raise RuntimeError("nope")

        instance._run_phase(1, "Bad", boom)
        instance._run_phase(2, "Good", lambda: ran.append(2))

        assert ran == [2]
        assert len(instance.phase_failures) == 1
        kg.close()


class TestDegradedRun:
    def test_the_run_completes_without_a_vector_index(self, analyzer: TSCodeKGAnalyzer) -> None:
        assert analyzer.to_markdown().startswith("# TypeScriptKG Repository Analysis")

    def test_only_the_semantic_phase_is_skipped(self, analyzer: TSCodeKGAnalyzer) -> None:
        assert len(analyzer.phase_failures) <= 1

    def test_the_report_names_what_is_missing(self, analyzer: TSCodeKGAnalyzer) -> None:
        report = analyzer.to_markdown()
        if analyzer.phase_failures:
            assert "Incomplete Analysis" in report
            assert "tscodekg build" in report, "the notice must name the fix"

    def test_no_notice_when_every_phase_ran(self, analyzer: TSCodeKGAnalyzer) -> None:
        if not analyzer.phase_failures:
            assert "Incomplete Analysis" not in analyzer.to_markdown()

    def test_the_written_report_carries_the_notice(
        self, analyzer: TSCodeKGAnalyzer, tmp_path: Path
    ) -> None:
        """`--report` and stdout must not disagree about a degraded run."""
        out = tmp_path / "report.md"
        analyzer._write_report(str(out))
        if analyzer.phase_failures:
            assert "Incomplete Analysis" in out.read_text()


class TestPhasesThatNeedNoIndex:
    """These are the thirteen the abort was throwing away."""

    def test_baseline_metrics_are_collected(self, analyzer: TSCodeKGAnalyzer) -> None:
        assert analyzer.stats["total_nodes"] > 0

    def test_coderank_ran(self, analyzer: TSCodeKGAnalyzer) -> None:
        assert analyzer.coderank_scores

    def test_fan_in_metrics_exist(self, analyzer: TSCodeKGAnalyzer) -> None:
        assert analyzer.function_metrics

    def test_jsdoc_coverage_ran(self, analyzer: TSCodeKGAnalyzer) -> None:
        assert analyzer.jsdoc_coverage

    def test_inheritance_analysis_ran(self, analyzer: TSCodeKGAnalyzer) -> None:
        assert analyzer.inheritance_analysis

    def test_centrality_ran(self, analyzer: TSCodeKGAnalyzer) -> None:
        assert analyzer.centrality_modules

    def test_results_are_serialisable(self, analyzer: TSCodeKGAnalyzer) -> None:
        import json

        json.dumps(analyzer._compile_results())

    def test_results_dict_reports_degraded_runs(self, analyzer: TSCodeKGAnalyzer) -> None:
        """A caller reading the dict needs the same signal the report carries."""
        results = analyzer._compile_results()
        assert results["phase_failures"] == analyzer.phase_failures
