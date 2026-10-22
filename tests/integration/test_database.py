"""Integration tests: schema, repositories, CRUD services and all 25 queries.

Run with a configured DATABASE_URL (seeded). Each test cleans up after itself.
"""
import pytest
from sqlalchemy import text

from analytics.registry import QUERIES
from analytics.runner import run_query, run_read_only
from core.exceptions import RecordInUseError, ValidationError

pytestmark = pytest.mark.integration


def test_all_tables_exist(db_engine):
    with db_engine.connect() as conn:
        tables = set(conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        ).scalars())
    assert {"teams", "venues", "players", "series", "matches", "batting_innings",
            "bowling_innings", "player_format_stats", "ingestion_log"} <= tables


@pytest.mark.parametrize("spec", QUERIES, ids=lambda q: f"Q{q.number:02d}")
def test_every_query_returns_rows(db_engine, spec):
    assert len(run_query(spec)) > 0, f"{spec.label} returned no rows - reseed the database?"


def test_constraint_rejects_team_playing_itself(db_engine):
    with pytest.raises(Exception):
        with db_engine.begin() as conn:
            conn.execute(text("INSERT INTO matches (match_description, match_format, match_date,"
                              " venue_id, team1_id, team2_id, match_status) VALUES "
                              "('t', 'ODI', '2026-01-01', 1, 1, 1, 'Upcoming')"))


def test_player_crud_roundtrip(db_engine):
    from services.player_service import PlayerService
    service = PlayerService()
    team_id = service.list_teams()[0]["team_id"]
    pid = service.create({"full_name": "Pytest Player", "team_id": team_id,
                          "playing_role": "Bowler"})
    try:
        assert service.get(pid).full_name == "Pytest Player"
        service.update(pid, {"full_name": "Pytest Player Two", "team_id": team_id,
                             "playing_role": "All-rounder"})
        assert service.get(pid).playing_role == "All-rounder"
    finally:
        assert service.delete(pid)
    assert service.get(pid) is None


def test_invalid_player_is_rejected(db_engine):
    from services.player_service import PlayerService
    with pytest.raises(ValidationError):
        PlayerService().create({"full_name": "", "team_id": 1, "playing_role": "Batter"})


def test_delete_player_with_history_is_blocked(db_engine):
    from services.player_service import PlayerService
    with db_engine.connect() as conn:
        pid = conn.execute(text("SELECT player_id FROM batting_innings LIMIT 1")).scalar()
    with pytest.raises(RecordInUseError):
        PlayerService().delete(pid)


def test_read_only_console_blocks_writes(db_engine):
    with pytest.raises(ValueError):
        run_read_only("DELETE FROM players")
    with pytest.raises(ValueError):
        run_read_only("SELECT 1; DROP TABLE players")
    assert run_read_only("SELECT COUNT(*) AS n FROM teams")["n"][0] > 0
