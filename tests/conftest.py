"""
conftest.py — shared pytest fixtures for TypeScriptKG tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_ts_file() -> Path:
    """Return the path to the sample TypeScript fixture."""
    return FIXTURE_DIR / "sample.ts"


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Create a temporary repo directory with the sample fixture."""
    src = FIXTURE_DIR / "sample.ts"
    dest = tmp_path / "src" / "sample.ts"
    dest.parent.mkdir(parents=True)
    dest.write_text(src.read_text())
    return tmp_path
