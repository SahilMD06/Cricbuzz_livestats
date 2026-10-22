"""Ingestion end to end with a fake API client (no network, no quota).

Uses the JSON fixtures, then removes everything it created and restores any
team/venue links it added, so the real data is left exactly as it was.
"""
import pytest
from sqlalchemy import text

from core.exceptions import APINotFoundError
from services.ingestion_service import IngestionService

pytestmark = pytest.mark.integration
FIXTURE_MATCHES = (112345, 223344)
FIXTURE_PLAYERS = (1413, 8733, 1413000, 9311, 9312, 11, 12, 21)
FIXTURE_TEAMS = (2, 4, 7, 9)


class FakeClient:
    is_configured = True
    quota = {"limit": None, "remaining": None}

    def __init__(self, load):
        self.load = load

    def get_recent_matches(self):
        return self.load("recent")

    def get_scorecard(self, match_id):
        return self.load({112345: "scorecard_old", 223344: "scorecard_new"}[match_id])

    def get_match_info(self, match_id):
        if match_id == 223344:
            return self.load("match_info_new")
        raise APINotFoundError("no info in fixtures")

    def get_venue(self, venue_id):
        return {"ground": "Gaddafi Stadium", "city": "Lahore", "country": "Pakistan"}


@pytest.fixture
def clean_db(db_engine):
    with db_engine.connect() as conn:
        if conn.execute(text("SELECT COUNT(*) FROM matches WHERE cricbuzz_match_id = ANY(:ids)"),
                        {"ids": list(FIXTURE_MATCHES)}).scalar():
            pytest.skip("fixture match ids already present in this database")
        teams_before = set(conn.execute(text(
            "SELECT team_id FROM teams WHERE cricbuzz_team_id IS NULL")).scalars())
        venues_before = set(conn.execute(text("SELECT venue_id FROM venues")).scalars())
        venues_unlinked = set(conn.execute(text(
            "SELECT venue_id FROM venues WHERE cricbuzz_venue_id IS NULL")).scalars())
        log_max = conn.execute(text("SELECT COALESCE(MAX(log_id), 0) FROM ingestion_log")).scalar()
    yield
    with db_engine.begin() as conn:
        conn.execute(text("DELETE FROM matches WHERE cricbuzz_match_id = ANY(:ids)"),
                     {"ids": list(FIXTURE_MATCHES)})
        conn.execute(text("DELETE FROM players WHERE cricbuzz_player_id = ANY(:ids)"),
                     {"ids": list(FIXTURE_PLAYERS)})
        conn.execute(text("DELETE FROM series WHERE cricbuzz_series_id = 9237"))
        conn.execute(text("DELETE FROM venues WHERE NOT (venue_id = ANY(:ids))"),
                     {"ids": list(venues_before)})
        conn.execute(text("UPDATE venues SET cricbuzz_venue_id = NULL WHERE venue_id = ANY(:ids)"),
                     {"ids": list(venues_unlinked)})
        conn.execute(text("UPDATE teams SET cricbuzz_team_id = NULL WHERE team_id = ANY(:ids)"),
                     {"ids": list(teams_before)})
        conn.execute(text("DELETE FROM ingestion_log WHERE log_id > :m"), {"m": log_max})


def test_ingestion_is_idempotent(db_engine, clean_db, load_fixture):
    service = IngestionService(client=FakeClient(load_fixture), engine=db_engine)
    first = service.ingest_recent(limit=5)
    assert first.loaded == ["112345"] and not first.failed
    second = service.ingest_recent(limit=5)
    assert second.loaded == [] and second.skipped
    rows_a = service.ingest_match(223344)
    rows_b = service.ingest_match(223344)                 # reload replaces, never duplicates
    assert rows_a == rows_b == 3
    with db_engine.connect() as conn:
        result = conn.execute(text(
            "SELECT victory_type, victory_margin FROM matches WHERE cricbuzz_match_id = 223344"
        )).one()
    assert tuple(result) == ("runs", 23)
