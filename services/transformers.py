"""Pure functions that turn raw Cricbuzz JSON into clean Python rows.

No I/O happens here (no HTTP, no SQL), so every function can be unit-tested
against saved JSON files.

Robustness strategy - Cricbuzz has shipped two JSON styles:
    old: camelCase keys, dicts keyed bat_1/bat_2 ("batTeamDetails", "outDesc")
    new: lowercase keys, plain lists        ("batsman", "outdec")
1. ``normalize`` lower-cases every key, so both styles share key names.
2. ``first`` reads a value from whichever alternative key exists.
3. Results and tosses are read from structured fields when present, and
   otherwise parsed from the human-readable status ("India won by 6 wkts").
"""
from __future__ import annotations

import re
from typing import Any, Iterator

from models.entities import MatchCard, ScorecardInnings
from utils.formatters import (epoch_ms_to_date, overs_to_balls, to_float, to_int)

FORMAT_MAP = {"TEST": "Test", "ODI": "ODI", "T20": "T20I", "T20I": "T20I"}

_RESULT_RE = re.compile(
    r"^(?P<team>.+?)\s+won\s+by\s+(?P<innings>an\s+innings\s+and\s+)?(?P<margin>\d+)\s+"
    r"(?P<unit>runs?|wkts?|wickets?)", re.IGNORECASE)
_TOSS_RE = re.compile(
    r"^(?P<team>.+?)\s+(?:have\s+)?(?:won the toss and\s+)?(?:opt|opted|elected|chose)"
    r"\s+to\s+(?P<decision>bat|bowl|field)", re.IGNORECASE)


# --------------------------------------------------------------------------
#  Generic helpers
# --------------------------------------------------------------------------
def normalize(obj: Any) -> Any:
    """Recursively lower-case all dict keys."""
    if isinstance(obj, dict):
        return {str(k).lower(): normalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize(v) for v in obj]
    return obj


def first(d: dict | None, *keys: str, default: Any = None) -> Any:
    """Return the value of the first key present (and not None) in ``d``."""
    if not isinstance(d, dict):
        return default
    for key in keys:
        if d.get(key) not in (None, ""):
            return d[key]
    return default


def map_format(raw: str | None) -> str | None:
    """'TEST' / 'ODI' / 'T20' -> 'Test' / 'ODI' / 'T20I'; others (T10...) -> None."""
    return FORMAT_MAP.get(str(raw or "").strip().upper())


def map_role(raw: str | None) -> str:
    """Cricbuzz role text -> one of our four allowed playing roles."""
    text = str(raw or "").lower().replace(" ", "").replace("-", "")
    if "wk" in text or "keeper" in text:
        return "Wicket-keeper"
    if "allrounder" in text:
        return "All-rounder"
    if "bowl" in text:
        return "Bowler"
    return "Batsman"


def _ordered_entries(container: Any) -> list[dict]:
    """Return list entries in order, for a list or a {'bat_1': {...}} dict."""
    if isinstance(container, list):
        return [e for e in container if isinstance(e, dict)]
    if isinstance(container, dict):
        def order(key: str) -> int:
            digits = re.sub(r"\D", "", key)
            return int(digits) if digits else 0
        return [container[k] for k in sorted(container, key=order)
                if isinstance(container[k], dict)]
    return []


def _team(d: dict | None) -> dict:
    """Normalise a team block from either API style."""
    d = d or {}
    return {"id": to_int(first(d, "id", "teamid")),
            "name": first(d, "name", "teamname", default=""),
            "short": first(d, "shortname", "teamsname", "sname", default="")}


# --------------------------------------------------------------------------
#  Match lists (live / recent / upcoming)
# --------------------------------------------------------------------------
def iter_matches(payload: dict,
                 international_only: bool = False) -> Iterator[tuple[str, dict, dict]]:
    """Yield (series_name, match_info, match_score) for every real match.

    Skips advert entries mixed into ``seriesMatches``.
    """
    data = normalize(payload or {})
    for type_block in data.get("typematches", []) or []:
        if international_only and str(type_block.get("matchtype", "")).lower() != "international":
            continue
        for series in type_block.get("seriesmatches", []) or []:
            wrapper = series.get("seriesadwrapper")
            if not wrapper:
                continue                                  # advert, not a series
            for match in wrapper.get("matches", []) or []:
                info = match.get("matchinfo") or {}
                if info.get("matchid") is None:
                    continue
                yield (wrapper.get("seriesname", ""), info, match.get("matchscore") or {})


def _team_score(score_block: dict | None) -> str:
    """{'inngs1': {...}, 'inngs2': {...}} -> '210/3 (38.4) & 150'."""
    parts = []
    for key in sorted((score_block or {}).keys()):
        inn = score_block[key] or {}
        runs = to_int(inn.get("runs"))
        if runs is None:
            continue
        wkts = to_int(inn.get("wickets"))
        text = f"{runs}" if wkts in (None, 10) else f"{runs}/{wkts}"
        if inn.get("overs") not in (None, ""):
            text += f" ({inn['overs']})"
        parts.append(text)
    return " & ".join(parts) or "-"


def to_match_card(series_name: str, info: dict, score: dict) -> MatchCard:
    """Build a MatchCard for the Live page from one match entry."""
    t1, t2 = _team(info.get("team1")), _team(info.get("team2"))
    venue = info.get("venueinfo") or {}
    venue_text = ", ".join(x for x in (first(venue, "ground", "name"), venue.get("city")) if x)
    return MatchCard(
        match_id=to_int(info.get("matchid")),
        series_name=series_name or info.get("seriesname", ""),
        description=first(info, "matchdesc", "matchdescription", default=""),
        match_format=map_format(info.get("matchformat")) or str(info.get("matchformat", "")),
        team1=t1["name"], team2=t2["name"], team1_short=t1["short"], team2_short=t2["short"],
        team1_score=_team_score(score.get("team1score")),
        team2_score=_team_score(score.get("team2score")),
        venue=venue_text, status=info.get("status", ""), state=info.get("state", ""),
        start_date=epoch_ms_to_date(first(info, "startdate", "matchstarttimestamp")),
    )


def match_cards(payload: dict) -> list[MatchCard]:
    """All match cards in a live/recent/upcoming payload."""
    return [to_match_card(s, i, sc) for s, i, sc in iter_matches(payload)]


# --------------------------------------------------------------------------
#  Results and toss
# --------------------------------------------------------------------------
def _resolve_team(name: str, teams: list[dict]) -> int | None:
    name = name.strip().lower()
    for t in teams:
        if name in (str(t["name"]).lower(), str(t["short"]).lower()):
            return t["id"]
    for t in teams:                                       # partial match fallback
        if t["name"] and (name in t["name"].lower() or t["name"].lower() in name):
            return t["id"]
    return None


def parse_result(status: str | None, result: dict | None, teams: list[dict]) -> dict:
    """Return winner (cricbuzz team id), victory_type and victory_margin."""
    out = {"winner_cb_id": None, "victory_type": None, "victory_margin": None}
    result = result or {}
    winner = to_int(first(result, "winningteamid", "winnerteamid"))
    margin = to_int(result.get("winningmargin"))
    if winner and margin:
        if result.get("winbyinnings"):
            vtype = "innings"
        elif result.get("winbyruns"):
            vtype = "runs"
        else:
            vtype = "wickets"
        return {"winner_cb_id": winner, "victory_type": vtype, "victory_margin": margin}

    text = (status or "").strip()
    low = text.lower()
    if "tied" in low or "tie" == str(result.get("resulttype", "")).lower():
        out["victory_type"] = "tie"
    elif "drawn" in low or "draw" == str(result.get("resulttype", "")).lower():
        out["victory_type"] = "draw"
    elif "no result" in low or "abandon" in low:
        out["victory_type"] = "no result"
    else:
        m = _RESULT_RE.match(text)
        if m:
            unit = m.group("unit").lower()
            out.update(
                winner_cb_id=_resolve_team(m.group("team"), teams),
                victory_margin=int(m.group("margin")),
                victory_type="innings" if m.group("innings") else
                ("runs" if unit.startswith("run") else "wickets"))
    return out


def parse_toss(toss: dict | None, toss_text: str | None, teams: list[dict]) -> dict:
    """Return toss winner (cricbuzz team id) and decision ('bat'/'bowl')."""
    toss = toss or {}
    winner = to_int(first(toss, "tosswinnerid", "winnerid"))
    decision = str(first(toss, "decision", default="")).lower()
    if not winner and toss_text:
        m = _TOSS_RE.match(toss_text.strip())
        if m:
            winner = _resolve_team(m.group("team"), teams)
            decision = m.group("decision").lower()
    if not winner or not decision:
        return {"toss_winner_cb_id": None, "toss_decision": None}
    return {"toss_winner_cb_id": winner,
            "toss_decision": "bat" if decision.startswith("bat") else "bowl"}


# --------------------------------------------------------------------------
#  Scorecard
# --------------------------------------------------------------------------
def parse_match_meta(*payloads: dict) -> dict:
    """Extract match-level fields from scorecard and/or match-info payloads."""
    header: dict = {}
    for raw in payloads:
        data = normalize(raw or {})
        for candidate in (data.get("matchheader"), data.get("matchinfo"), data):
            if isinstance(candidate, dict) and candidate.get("matchid") is not None:
                for k, v in candidate.items():
                    header.setdefault(k, v)
        if data.get("venueinfo") and "venueinfo" not in header:
            header["venueinfo"] = data["venueinfo"]
        if data.get("status") and "status" not in header:
            header["status"] = data["status"]

    teams = [_team(header.get("team1")), _team(header.get("team2"))]
    venue = first(header, "venue", "venueinfo", default={}) or {}
    toss_block = first(header, "tossresults", default={})
    meta = {
        "cricbuzz_match_id": to_int(header.get("matchid")),
        "match_description": first(header, "matchdescription", "matchdesc", default="Match"),
        "match_format": map_format(header.get("matchformat")),
        "match_date": epoch_ms_to_date(first(header, "matchstarttimestamp", "startdate")),
        "status": header.get("status", ""),
        "state": str(header.get("state", "")),
        "is_complete": bool(header.get("complete") or header.get("ismatchcomplete")
                            or str(header.get("state", "")).lower() in ("complete", "completed")),
        "series_cb_id": to_int(header.get("seriesid")),
        "series_name": header.get("seriesname", ""),
        "team1": teams[0], "team2": teams[1],
        "venue": {"id": to_int(venue.get("id")),
                  "name": first(venue, "name", "ground", default=""),
                  "city": venue.get("city", ""),
                  "country": venue.get("country", "")},
    }
    meta.update(parse_toss(toss_block, first(header, "tossstatus", default=None), teams))
    meta.update(parse_result(meta["status"], header.get("result"), teams))
    return meta


def _batter_row(entry: dict, position: int) -> dict | None:
    """One batter; returns None for 'did not bat' placeholders."""
    runs = to_int(entry.get("runs"), 0)
    balls = to_int(entry.get("balls"), 0)
    dismissal = str(first(entry, "outdesc", "outdec", "dismissal", default="")).strip()
    if not dismissal and runs == 0 and balls == 0:
        return None
    is_out = dismissal.lower() not in ("", "not out", "batting", "retired hurt")
    return {
        "cricbuzz_player_id": to_int(first(entry, "batid", "id", "playerid")),
        "name": first(entry, "batname", "name", "fullname", default="Unknown"),
        "batting_position": position,
        "runs": runs, "balls_faced": balls,
        "fours": to_int(entry.get("fours"), 0), "sixes": to_int(entry.get("sixes"), 0),
        "strike_rate": to_float(first(entry, "strikerate", "strkrate")),
        "is_out": is_out, "dismissal": dismissal or "not out",
        "is_keeper": bool(entry.get("iskeeper")),
    }


def _bowler_row(entry: dict) -> dict:
    balls = overs_to_balls(entry.get("overs"))
    return {
        "cricbuzz_player_id": to_int(first(entry, "bowlerid", "bowlid", "id", "playerid")),
        "name": first(entry, "bowlname", "name", "fullname", default="Unknown"),
        "overs": str(entry.get("overs", "0")), "balls_bowled": balls,
        "maidens": to_int(entry.get("maidens"), 0),
        "runs_conceded": to_int(entry.get("runs"), 0),
        "wickets": to_int(entry.get("wickets"), 0),
        "economy": to_float(entry.get("economy")),
    }


def parse_scorecard(payload: dict, meta: dict | None = None) -> list[ScorecardInnings]:
    """Parse every innings of a scorecard (old or new API style)."""
    data = normalize(payload or {})
    meta = meta or parse_match_meta(payload)
    teams = [meta["team1"], meta["team2"]]
    innings_list = first(data, "scorecard", "scorecards", default=[]) or []
    parsed: list[ScorecardInnings] = []
    for idx, inn in enumerate(innings_list, start=1):
        bat_team = inn.get("batteamdetails") or {}
        bowl_team = inn.get("bowlteamdetails") or {}
        batters = _ordered_entries(first(bat_team, "batsmendata", default=None)
                                   or first(inn, "batsman", "batsmen", default=[]))
        bowlers = _ordered_entries(first(bowl_team, "bowlersdata", default=None)
                                   or first(inn, "bowler", "bowlers", default=[]))
        batting = [r for pos, e in enumerate(batters, start=1)
                   if (r := _batter_row(e, pos)) is not None]
        bowling = [_bowler_row(e) for e in bowlers]
        score = inn.get("scoredetails") or inn
        bat_name = first(bat_team, "batteamname", default=None) or first(
            inn, "batteamname", default="")
        bat_id = to_int(first(bat_team, "batteamid", default=None)
                        or first(inn, "batteamid", default=None)) or _resolve_team(bat_name, teams)
        other = next((t for t in teams if t["id"] and t["id"] != bat_id), {"name": "", "id": None})
        card = ScorecardInnings(
            innings_no=to_int(first(inn, "inningsid", default=idx)) or idx,
            batting_team=bat_name or next((t["name"] for t in teams if t["id"] == bat_id), ""),
            bowling_team=first(bowl_team, "bowlteamname", default=None) or other["name"],
            runs=to_int(first(score, "runs", "score")), wickets=to_int(score.get("wickets")),
            overs=str(score.get("overs")) if score.get("overs") is not None else None,
            batting=batting, bowling=bowling,
            batting_team_cb_id=bat_id, bowling_team_cb_id=other["id"])
        parsed.append(card)
    return parsed


# --------------------------------------------------------------------------
#  Stats, players, venues
# --------------------------------------------------------------------------
def parse_stats_table(payload: dict) -> tuple[list[str], list[list[str]]]:
    """Generic {'headers': [...], 'values': [{'values': [...]}]} -> (headers, rows)."""
    data = normalize(payload or {})
    headers = [str(h) for h in data.get("headers", []) or []]
    rows = [list(v.get("values", [])) for v in data.get("values", []) or []
            if isinstance(v, dict)]
    return headers, rows


def parse_top_stats(payload: dict) -> list[dict]:
    """Top-stats leaderboard -> list of dicts (first hidden column = player id)."""
    headers, rows = parse_stats_table(payload)
    out = []
    for row in rows:
        if len(row) == len(headers) + 1:              # leading hidden player id
            record = {"player_id": to_int(row[0])}
            record.update(dict(zip(headers, row[1:])))
        else:
            record = dict(zip(headers, row))
        out.append(record)
    return out


def parse_player_profile(payload: dict) -> dict:
    """Player info -> fields for the players table."""
    data = normalize(payload or {})
    return {
        "cricbuzz_player_id": to_int(data.get("id")),
        "full_name": first(data, "name", "fullname", default="Unknown"),
        "playing_role": map_role(data.get("role")),
        "batting_style": _batting_style(data.get("bat")),
        "bowling_style": first(data, "bowl", default=None),
        "team_name": first(data, "intlteam", "teamname", default=None),
    }


def _batting_style(raw: str | None) -> str | None:
    text = str(raw or "").lower()
    if "left" in text:
        return "Left-hand bat"
    if "right" in text:
        return "Right-hand bat"
    return None


_CAREER_FIELDS = {
    # stat-row label (lowercase) -> output column
    "matches": "matches", "innings": "innings", "runs": "runs", "highest": "highest_score",
    "average": "batting_average", "sr": "batting_strike_rate", "100s": "hundreds",
    "50s": "fifties", "not out": "not_outs",
}
_BOWL_FIELDS = {"balls": "balls_bowled", "runs": "runs_conceded", "wickets": "wickets",
                "avg": "bowling_average", "eco": "economy", "matches": "matches"}


def parse_career(batting: dict | None, bowling: dict | None) -> list[dict]:
    """Un-pivot career batting/bowling tables into one row per format.

    The API returns rows = statistics and columns = formats; our table needs
    rows = formats. Non-international columns (e.g. IPL) are dropped.
    """
    per_format: dict[str, dict] = {}

    def absorb(payload: dict | None, fields: dict[str, str]) -> None:
        headers, rows = parse_stats_table(payload or {})
        for row in rows:
            if not row:
                continue
            label = str(row[0]).strip().lower()
            column = fields.get(label)
            if not column:
                continue
            for col_name, value in zip(headers[1:], row[1:]):
                fmt = map_format(col_name)
                if not fmt:
                    continue
                rec = per_format.setdefault(fmt, {"match_format": fmt})
                parse = to_float if column in ("batting_average", "batting_strike_rate",
                                               "bowling_average", "economy") else to_int
                parsed = parse(value)
                if column == "matches" and "matches" in rec and parsed is not None:
                    parsed = max(rec["matches"] or 0, parsed)
                rec[column] = parsed

    absorb(batting, _CAREER_FIELDS)
    absorb(bowling, _BOWL_FIELDS)
    rows = []
    for rec in per_format.values():
        if not rec.get("matches"):
            continue
        rec.pop("not_outs", None)
        rows.append(rec)
    return rows


def parse_venue(payload: dict) -> dict:
    """Venue info -> name, city, country, capacity."""
    data = normalize(payload or {})
    return {"venue_name": first(data, "ground", "name", default="Unknown ground"),
            "city": first(data, "city", default="Unknown"),
            "country": first(data, "country", default="Unknown"),
            "capacity": _capacity(data.get("capacity"))}


def _capacity(raw) -> int | None:
    """'1,32,000' / '32000 (approx)' / 32000 -> int; anything else -> None."""
    match = re.search(r"\d[\d,]*", str(raw or ""))
    value = to_int(match.group(0)) if match else None
    return value if value and value > 0 else None
