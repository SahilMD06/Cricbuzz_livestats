"""Shared pytest fixtures.

Unit tests need nothing but Python. Integration tests use the database from
DATABASE_URL and are skipped automatically when it is not reachable.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture():
    """load_fixture('scorecard_old') -> parsed JSON from tests/fixtures/."""
    def _load(name: str) -> dict:
        return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return _load


@pytest.fixture(scope="session")
def db_engine():
    """A live engine, or skip the test if the database is not available."""
    from config import ConfigError
    from core.exceptions import AppError
    from utils.db_connection import check_connection, get_engine
    try:
        check_connection()
    except (AppError, ConfigError) as exc:
        pytest.skip(f"database not available: {exc}")
    return get_engine()
