"""MatchService - validation and business rules for match CRUD."""
from __future__ import annotations

from datetime import date

import pandas as pd

from core.exceptions import ValidationError
from database import (InningsRepository, MatchRepository, SeriesRepository, TeamRepository,
                      VenueRepository)
from models.entities import Match
from utils.validators import validate_match


class MatchService:
    """Pages call this; it validates input and talks to the repositories."""

    def __init__(self, matches: MatchRepository | None = None) -> None:
        self.matches = matches or MatchRepository()
        self.teams = TeamRepository(self.matches.engine)
        self.venues = VenueRepository(self.matches.engine)
        self.series = SeriesRepository(self.matches.engine)
        self.innings = InningsRepository(self.matches.engine)

    # lookups for form dropdowns
    def list_teams(self) -> list[dict]:
        return self.teams.list_all()

    def list_venues(self) -> list[dict]:
        return self.venues.list_all()

    def list_series(self) -> list[dict]:
        return self.series.list_all()

    def search(self, **filters) -> pd.DataFrame:
        return self.matches.search(**filters)

    def get(self, match_id: int) -> Match | None:
        return self.matches.get(match_id)

    def summary_row(self, match_id: int) -> dict | None:
        return self.matches.summary_row(match_id)

    def scorecard(self, match_id: int) -> tuple[pd.DataFrame, pd.DataFrame]:
        return self.innings.scorecard(match_id)

    def summary(self) -> dict:
        return self.matches.summary()

    def _build(self, data: dict) -> Match:
        status = data.get("match_status") or "Completed"
        completed = status == "Completed"
        vtype = data.get("victory_type") if completed or status == "Abandoned" else None
        decided = vtype in ("runs", "wickets", "innings")
        toss_winner = data.get("toss_winner_id")
        match = Match(
            match_description=(data.get("match_description") or "").strip(),
            match_format=data.get("match_format"),
            match_date=data.get("match_date") if isinstance(data.get("match_date"), date)
            else None,
            venue_id=data.get("venue_id"),
            team1_id=data.get("team1_id"), team2_id=data.get("team2_id"),
            match_status=status,
            series_id=data.get("series_id"),
            toss_winner_id=toss_winner,
            toss_decision=data.get("toss_decision") if toss_winner else None,
            winner_id=data.get("winner_id") if decided else None,
            victory_margin=data.get("victory_margin") if decided else None,
            victory_type=vtype,
            source="manual")
        errors = validate_match(match)
        if not match.match_date:
            errors.insert(0, "Match date is required.")
        if errors:
            raise ValidationError(errors)
        return match

    def create(self, data: dict) -> int:
        return self.matches.create(self._build(data))

    def update(self, match_id: int, data: dict) -> bool:
        return self.matches.update(match_id, self._build(data))

    def delete(self, match_id: int) -> bool:
        """Delete a match and (via ON DELETE CASCADE) its innings."""
        return self.matches.delete(match_id)
