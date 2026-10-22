"""The seed generator must only produce data the schema would accept."""
from collections import Counter
from datetime import date

import pytest

from scripts.seed_data import SeedGenerator

TODAY = date(2026, 10, 22)


@pytest.fixture(scope="module")
def rows():
    return SeedGenerator(TODAY).generate()


def test_deterministic():
    a = SeedGenerator(TODAY).generate()
    b = SeedGenerator(TODAY).generate()
    assert [r["runs"] for r in a.batting_innings] == [r["runs"] for r in b.batting_innings]


def test_match_rules(rows):
    for m in rows.matches:
        assert m["team1_id"] != m["team2_id"]
        if m["match_status"] == "Completed":
            assert m["victory_type"] is not None
            assert m["winner_id"] in (None, m["team1_id"], m["team2_id"])
            if m["victory_type"] == "wickets":
                assert 1 <= m["victory_margin"] <= 10
            if m["victory_margin"] is not None:
                assert m["victory_margin"] > 0
        else:
            assert m["match_date"] >= TODAY


def test_batting_rules(rows):
    positions = Counter((r["match_id"], r["innings_no"], r["batting_position"])
                        for r in rows.batting_innings)
    assert max(positions.values()) == 1                           # unique per innings
    for r in rows.batting_innings:
        assert r["fours"] * 4 + r["sixes"] * 6 <= r["runs"]
        assert 1 <= r["batting_position"] <= 11


def test_at_most_ten_wickets_per_innings(rows):
    outs = Counter((r["match_id"], r["innings_no"]) for r in rows.batting_innings if r["is_out"])
    assert max(outs.values()) <= 10


def test_bowling_rules(rows):
    for r in rows.bowling_innings:
        assert r["balls_bowled"] >= 1 and 0 <= r["wickets"] <= 10


def test_recent_matches_exist(rows):
    recent = [m for m in rows.matches if m["match_status"] == "Completed"
              and (TODAY - m["match_date"]).days <= 30]
    assert len(recent) >= 1
