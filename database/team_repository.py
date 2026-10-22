"""TeamRepository - SQL for the ``teams`` table."""
from __future__ import annotations

from sqlalchemy import Connection, text

from database.base_repository import BaseRepository


class TeamRepository(BaseRepository):
    """Read teams; upsert teams discovered through the API."""

    def list_all(self) -> list[dict]:
        return self.fetch_all(
            "SELECT team_id, team_name, short_name, country FROM teams ORDER BY team_name")

    def get(self, team_id: int) -> dict | None:
        return self.fetch_one("SELECT * FROM teams WHERE team_id = :id", {"id": team_id})

    @staticmethod
    def upsert_api(conn: Connection, cb_id: int | None, name: str, short: str | None,
                   country: str | None = None) -> int:
        """Return team_id for an API team, creating or linking it as needed.

        1. Already linked by Cricbuzz id -> reuse it.
        2. Same name exists (e.g. a seed team 'India') -> link the Cricbuzz id.
        3. Otherwise insert a new team.
        """
        if cb_id is not None:
            found = conn.execute(text("SELECT team_id FROM teams WHERE cricbuzz_team_id = :cb"),
                                 {"cb": cb_id}).scalar()
            if found:
                return found
        return conn.execute(text("""
            INSERT INTO teams (cricbuzz_team_id, team_name, short_name, country)
            VALUES (:cb, :name, :short, :country)
            ON CONFLICT (team_name) DO UPDATE
               SET cricbuzz_team_id = COALESCE(teams.cricbuzz_team_id, EXCLUDED.cricbuzz_team_id),
                   short_name       = COALESCE(teams.short_name, EXCLUDED.short_name)
            RETURNING team_id
        """), {"cb": cb_id, "name": name, "short": short or None,
               "country": country or name}).scalar_one()
