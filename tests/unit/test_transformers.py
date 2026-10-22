"""JSON -> row transformers, against both Cricbuzz JSON styles."""
from datetime import date

from services import transformers as tf


def test_normalize_lowercases_nested_keys():
    assert tf.normalize({"A": [{"bB": 1}]}) == {"a": [{"bb": 1}]}


def test_match_cards_skip_ads(load_fixture):
    cards = tf.match_cards(load_fixture("recent"))
    assert [c.match_id for c in cards] == [112345, 5]
    india = cards[0]
    assert india.team2 == "India" and india.team2_score == "230/2 (38.3)"
    assert india.start_date == date(2025, 10, 20)


def test_iter_matches_international_only(load_fixture):
    ids = [i["matchid"] for _, i, _ in tf.iter_matches(load_fixture("recent"), True)]
    assert ids == [112345]


def test_old_style_scorecard(load_fixture):
    raw = load_fixture("scorecard_old")
    meta = tf.parse_match_meta(raw)
    assert meta["match_format"] == "ODI"
    assert (meta["winner_cb_id"], meta["victory_type"], meta["victory_margin"]) == (2, "wickets", 8)
    assert (meta["toss_winner_cb_id"], meta["toss_decision"]) == (4, "bat")
    innings = tf.parse_scorecard(raw, meta)
    batting = innings[0].batting
    # bat_10 is a 'did not bat' placeholder and is dropped; bat_3 sorts before bat_10
    assert [b["name"] for b in batting] == ["Rohit Sharma", "Shubman Gill", "Virat Kohli"]
    assert [b["batting_position"] for b in batting] == [1, 2, 3]
    assert batting[1]["is_out"] is False
    assert innings[0].bowling[0]["balls_bowled"] == 51          # 8.3 overs
    assert innings[0].batting_team_cb_id == 2 and innings[0].bowling_team_cb_id == 4


def test_new_style_scorecard_with_match_info(load_fixture):
    meta = tf.parse_match_meta(load_fixture("scorecard_new"), load_fixture("match_info_new"))
    assert meta["match_format"] == "T20I"
    assert meta["venue"]["name"] == "Gaddafi Stadium"
    assert (meta["toss_winner_cb_id"], meta["toss_decision"]) == (9, "bowl")   # from text
    assert (meta["winner_cb_id"], meta["victory_type"]) == (7, "runs")         # from status
    inn = tf.parse_scorecard(load_fixture("scorecard_new"), meta)[0]
    assert inn.batting_team_cb_id == 9 and inn.bowling_team_cb_id == 7
    assert inn.batting[0]["dismissal"] == "c Rizwan b Afridi"


def test_result_text_variants():
    teams = [{"id": 5, "name": "New Zealand", "short": "NZ"},
             {"id": 6, "name": "Sri Lanka", "short": "SL"}]
    r = tf.parse_result("New Zealand won by an innings and 32 runs", {}, teams)
    assert r == {"winner_cb_id": 5, "victory_type": "innings", "victory_margin": 32}
    assert tf.parse_result("SL won by 3 wkts", {}, teams)["winner_cb_id"] == 6
    assert tf.parse_result("Match drawn", {}, teams)["victory_type"] == "draw"
    assert tf.parse_result("Match tied (NZ won the Super Over)", {}, teams)["victory_type"] == "tie"
    assert tf.parse_result("No result due to rain", {}, teams)["victory_type"] == "no result"


def test_format_and_role_mapping():
    formats = [tf.map_format(f) for f in ("TEST", "ODI", "T20", "T10")]
    assert formats == ["Test", "ODI", "T20I", None]
    assert tf.map_role("WK-Batsman") == "Wicket-keeper"
    assert tf.map_role("Batting Allrounder") == "All-rounder"
    assert tf.map_role("Bowler") == "Bowler"
    assert tf.map_role(None) == "Batsman"


def test_career_unpivot_drops_ipl(load_fixture):
    rows = tf.parse_career(load_fixture("career_batting"), load_fixture("career_bowling"))
    by_fmt = {r["match_format"]: r for r in rows}
    assert set(by_fmt) == {"Test", "ODI", "T20I"}
    assert by_fmt["ODI"]["runs"] == 14181 and by_fmt["ODI"]["hundreds"] == 51
    assert by_fmt["Test"]["bowling_average"] is None            # '-' in the feed
    assert by_fmt["T20I"]["wickets"] == 4


def test_top_stats_and_venue(load_fixture):
    rows = tf.parse_top_stats(load_fixture("topstats"))
    assert rows[0]["player_id"] == 1413 and rows[0]["Batter"] == "Virat Kohli"
    assert tf.parse_venue(load_fixture("venue"))["capacity"] == 132000


def test_real_cricbuzz_response_2026(load_fixture):
    """A real Cricbuzz v2 response (IND v NZ, 1st T20I, 22 Oct 2026)."""
    meta = tf.parse_match_meta(load_fixture("real_scorecard_161190"),
                               load_fixture("real_info_161190"))
    assert (meta["match_format"], meta["match_description"]) == ("T20I", "1st T20I")
    assert (meta["toss_winner_cb_id"], meta["toss_decision"]) == (2, "bowl")
    assert (meta["winner_cb_id"], meta["victory_type"], meta["victory_margin"]) == (2, "wickets", 4)
    assert meta["venue"] == {"id": 371, "name": "Hagley Oval", "city": "Christchurch",
                             "country": "New Zealand", "capacity": 20000}
    first, second = tf.parse_scorecard(load_fixture("real_scorecard_161190"), meta)
    assert (first.batting_team_cb_id, first.bowling_team_cb_id) == (13, 2)
    assert len(first.batting) == 6                       # 5 'did not bat' entries dropped
    assert first.batting[3]["name"] == "Glenn Phillips" and not first.batting[3]["is_out"]
    assert second.bowling[0]["balls_bowled"] == 22       # 3.4 overs
