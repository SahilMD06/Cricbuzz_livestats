"""Cricbuzz (RapidAPI) endpoint paths and code tables.

Paths live here as named constants instead of magic strings scattered across
the code, so an endpoint change is a one-line fix.
"""
from __future__ import annotations

# ---- Matches -------------------------------------------------------------
LIVE_MATCHES = "/matches/v1/live"
RECENT_MATCHES = "/matches/v1/recent"
UPCOMING_MATCHES = "/matches/v1/upcoming"

# ---- Match centre ----------------------------------------------------------
MATCH_INFO = "/mcenter/v1/{match_id}"
SCORECARD = "/mcenter/v1/{match_id}/scard"
SCORECARD_ALT = "/mcenter/v1/{match_id}/hscard"   # newer API versions

# ---- Players ---------------------------------------------------------------
PLAYER_SEARCH = "/stats/v1/player/search"           # ?plrN=<name>
PLAYER_INFO = "/stats/v1/player/{player_id}"
PLAYER_BATTING = "/stats/v1/player/{player_id}/batting"
PLAYER_BOWLING = "/stats/v1/player/{player_id}/bowling"

# ---- Stats -----------------------------------------------------------------
TOP_STATS_TYPES = "/stats/v1/topstats"
TOP_STATS = "/stats/v1/topstats/0"                  # ?statsType=..&matchType=..

# ---- Reference -------------------------------------------------------------
TEAMS_INTERNATIONAL = "/teams/v1/international"
VENUE_INFO = "/venues/v1/{venue_id}"
SERIES_INTERNATIONAL = "/series/v1/international"

# matchType codes used by the top-stats endpoint.
MATCH_TYPE_CODES: dict[str, int] = {"Test": 1, "ODI": 2, "T20I": 3}

# statsType values offered on the Top Stats page: (api value, label, kind).
TOP_STATS_CATEGORIES: list[tuple[str, str, str]] = [
    ("mostRuns", "Most runs", "batting"),
    ("highestScore", "Highest individual score", "batting"),
    ("highestAvg", "Best batting average", "batting"),
    ("highestSr", "Best strike rate", "batting"),
    ("mostHundreds", "Most hundreds", "batting"),
    ("mostFifties", "Most fifties", "batting"),
    ("mostSixes", "Most sixes", "batting"),
    ("mostFours", "Most fours", "batting"),
    ("mostWickets", "Most wickets", "bowling"),
    ("lowestAvg", "Best bowling average", "bowling"),
    ("lowestEcon", "Best economy", "bowling"),
    ("bestBowlingInnings", "Best bowling in an innings", "bowling"),
    ("mostFiveWickets", "Most five-wicket hauls", "bowling"),
]
