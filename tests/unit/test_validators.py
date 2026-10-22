"""Input validation rules for CRUD forms."""
from datetime import date, timedelta

from models.entities import Match, Player
from utils.validators import validate_match, validate_player


def make_player(**kw) -> Player:
    base = dict(full_name="Test Player", team_id=1, playing_role="Batsman")
    return Player(**(base | kw))


def make_match(**kw) -> Match:
    base = dict(match_description="1st ODI", match_format="ODI", match_date=date(2025, 1, 1),
                venue_id=1, team1_id=1, team2_id=2, match_status="Completed",
                toss_winner_id=1, toss_decision="bat", winner_id=1, victory_margin=20,
                victory_type="runs")
    return Match(**(base | kw))


def test_valid_player_has_no_errors():
    assert validate_player(make_player()) == []


def test_player_rules():
    assert validate_player(make_player(full_name="  "))
    assert validate_player(make_player(playing_role="Batter"))
    assert validate_player(make_player(full_name="R2D2"))
    assert validate_player(make_player(date_of_birth=date.today() + timedelta(days=1)))
    assert validate_player(make_player(batting_style="Both hands"))


def test_valid_match_has_no_errors():
    assert validate_match(make_match()) == []


def test_team_cannot_play_itself():
    assert any("itself" in e for e in validate_match(make_match(team2_id=1)))


def test_winner_must_be_a_participant():
    assert validate_match(make_match(winner_id=3))


def test_wicket_margin_max_ten():
    assert validate_match(make_match(victory_type="wickets", victory_margin=11))


def test_draw_has_no_winner():
    assert validate_match(make_match(victory_type="draw"))          # winner still set
    assert validate_match(make_match(victory_type="draw", winner_id=None,
                                     victory_margin=None)) == []


def test_toss_fields_go_together():
    assert validate_match(make_match(toss_decision=None))


def test_upcoming_match_has_no_result():
    errors = validate_match(make_match(match_status="Upcoming",
                                       match_date=date.today() + timedelta(days=3)))
    assert any("result" in e for e in errors)
