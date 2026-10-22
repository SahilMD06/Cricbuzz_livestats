"""PlayerService - validation and business rules for player CRUD."""
from __future__ import annotations

from datetime import date

import pandas as pd

from core.exceptions import RecordInUseError, ValidationError
from database import PlayerRepository, TeamRepository
from models.entities import Player
from utils.validators import validate_player


def _clean(value):
    """Trim strings; turn empty strings into None."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class PlayerService:
    """Pages call this; it validates input and talks to the repositories."""

    def __init__(self, players: PlayerRepository | None = None,
                 teams: TeamRepository | None = None) -> None:
        self.players = players or PlayerRepository()
        self.teams = teams or TeamRepository()

    def list_teams(self) -> list[dict]:
        return self.teams.list_all()

    def search(self, name: str = "", team_id: int | None = None,
               role: str | None = None, limit: int = 200) -> pd.DataFrame:
        return self.players.search(name, team_id, role, limit)

    def get(self, player_id: int) -> Player | None:
        return self.players.get(player_id)

    def career(self, player_id: int) -> pd.DataFrame:
        return self.players.career_stats(player_id)

    def _build(self, data: dict, source: str = "manual") -> Player:
        dob = data.get("date_of_birth")
        player = Player(
            full_name=_clean(data.get("full_name")) or "",
            team_id=data.get("team_id"),
            playing_role=data.get("playing_role"),
            batting_style=_clean(data.get("batting_style")),
            bowling_style=_clean(data.get("bowling_style")),
            date_of_birth=dob if isinstance(dob, date) else None,
            source=source)
        errors = validate_player(player)
        if errors:
            raise ValidationError(errors)
        return player

    def create(self, data: dict) -> int:
        """Validate and insert; returns the new player_id."""
        return self.players.create(self._build(data))

    def update(self, player_id: int, data: dict) -> bool:
        """Validate and update; returns False if the player no longer exists."""
        return self.players.update(player_id, self._build(data))

    def delete(self, player_id: int) -> bool:
        """Delete a player, explaining clearly when match history blocks it."""
        try:
            return self.players.delete(player_id)
        except RecordInUseError as exc:
            counts = self.players.history_counts(player_id)
            raise RecordInUseError(
                f"Cannot delete: this player has {counts.get('batting', 0)} batting and "
                f"{counts.get('bowling', 0)} bowling innings on record. Deleting them would "
                "corrupt match history.", detail=exc.detail) from exc
