"""Domain dataclasses passed between layers.

A typed ``Player`` catches a misspelled field immediately (TypeError), where a
plain dict would silently carry the typo three layers further.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date

PLAYING_ROLES: tuple[str, ...] = ("Batsman", "Bowler", "All-rounder", "Wicket-keeper")
MATCH_FORMATS: tuple[str, ...] = ("Test", "ODI", "T20I")
TOSS_DECISIONS: tuple[str, ...] = ("bat", "bowl")
VICTORY_TYPES: tuple[str, ...] = ("runs", "wickets", "innings", "tie", "draw", "no result")
MATCH_STATUSES: tuple[str, ...] = ("Upcoming", "Live", "Completed", "Abandoned")
BATTING_STYLES: tuple[str, ...] = ("Right-hand bat", "Left-hand bat")
BOWLING_STYLES: tuple[str, ...] = (
    "Right-arm fast", "Right-arm fast-medium", "Right-arm medium", "Left-arm fast",
    "Left-arm medium", "Right-arm offbreak", "Legbreak googly", "Slow left-arm orthodox",
    "Left-arm wrist-spin",
)


@dataclass
class Player:
    """A row of the ``players`` table."""

    full_name: str
    team_id: int
    playing_role: str
    batting_style: str | None = None
    bowling_style: str | None = None
    date_of_birth: date | None = None
    source: str = "manual"
    cricbuzz_player_id: int | None = None
    player_id: int | None = None

    def to_db(self) -> dict:
        """Columns for INSERT/UPDATE (excludes the generated primary key)."""
        data = asdict(self)
        data.pop("player_id")
        return data


@dataclass
class Match:
    """A row of the ``matches`` table."""

    match_description: str
    match_format: str
    match_date: date
    venue_id: int
    team1_id: int
    team2_id: int
    match_status: str = "Completed"
    series_id: int | None = None
    toss_winner_id: int | None = None
    toss_decision: str | None = None
    winner_id: int | None = None
    victory_margin: int | None = None
    victory_type: str | None = None
    source: str = "manual"
    cricbuzz_match_id: int | None = None
    match_id: int | None = None

    def to_db(self) -> dict:
        data = asdict(self)
        data.pop("match_id")
        return data


@dataclass
class ScorecardInnings:
    """One innings of a parsed API scorecard (used by the Live page)."""

    innings_no: int
    batting_team: str
    bowling_team: str
    runs: int | None
    wickets: int | None
    overs: str | None
    batting: list[dict] = field(default_factory=list)
    bowling: list[dict] = field(default_factory=list)
    batting_team_cb_id: int | None = None    # Cricbuzz team ids, for ingestion
    bowling_team_cb_id: int | None = None


@dataclass
class MatchCard:
    """A live/recent/upcoming match summary card (used by the Live page)."""

    match_id: int
    series_name: str
    description: str
    match_format: str
    team1: str
    team2: str
    team1_short: str
    team2_short: str
    team1_score: str
    team2_score: str
    venue: str
    status: str
    state: str
    start_date: date | None
