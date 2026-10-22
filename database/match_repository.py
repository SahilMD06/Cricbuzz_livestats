"""MatchRepository - SQL for the ``matches`` table (+ dashboard summary)."""
from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy import Connection, text

from database.base_repository import BaseRepository
from models.entities import Match

_MATCH_COLUMNS = ("series_id", "match_description", "match_format", "match_date", "venue_id",
                  "team1_id", "team2_id", "toss_winner_id", "toss_decision", "winner_id",
                  "victory_margin", "victory_type", "match_status", "source",
                  "cricbuzz_match_id")
_EDITABLE = tuple(c for c in _MATCH_COLUMNS if c not in ("source", "cricbuzz_match_id"))


class MatchRepository(BaseRepository):
    """CRUD for matches plus API upserts."""

    # ------------------------------------------------------------- read
    def search(self, match_format: str | None = None, team_id: int | None = None,
               status: str | None = None, date_from: date | None = None,
               date_to: date | None = None, limit: int = 200) -> pd.DataFrame:
        """Filtered match list using the v_match_summary view."""
        return self.fetch_df("""
            SELECT ms.match_id, ms.match_date, ms.match_format, ms.match_description,
                   ms.team1_name, ms.team2_name, ms.venue_name, ms.venue_city,
                   ms.result_text, ms.match_status, ms.source
            FROM v_match_summary ms
            JOIN matches m ON m.match_id = ms.match_id
            WHERE (CAST(:fmt AS VARCHAR) IS NULL OR ms.match_format = :fmt)
              AND (CAST(:team AS INTEGER) IS NULL OR :team IN (m.team1_id, m.team2_id))
              AND (CAST(:status AS VARCHAR) IS NULL OR ms.match_status = :status)
              AND (CAST(:dfrom AS DATE) IS NULL OR ms.match_date >= :dfrom)
              AND (CAST(:dto AS DATE) IS NULL OR ms.match_date <= :dto)
            ORDER BY ms.match_date DESC, ms.match_id DESC
            LIMIT :limit
        """, {"fmt": match_format, "team": team_id, "status": status,
              "dfrom": date_from, "dto": date_to, "limit": limit})

    def get(self, match_id: int) -> Match | None:
        row = self.fetch_one(f"SELECT match_id, {', '.join(_MATCH_COLUMNS)} "
                             "FROM matches WHERE match_id = :id", {"id": match_id})
        return Match(**row) if row else None

    def summary_row(self, match_id: int) -> dict | None:
        """One readable match row (team/venue names, result text)."""
        return self.fetch_one("SELECT * FROM v_match_summary WHERE match_id = :id",
                              {"id": match_id})

    def summary(self) -> dict:
        """Row counts for the Home page."""
        return self.fetch_one("""
            SELECT (SELECT COUNT(*) FROM teams)    AS teams,
                   (SELECT COUNT(*) FROM venues)   AS venues,
                   (SELECT COUNT(*) FROM players)  AS players,
                   (SELECT COUNT(*) FROM series)   AS series,
                   (SELECT COUNT(*) FROM matches)  AS matches,
                   (SELECT COUNT(*) FROM matches WHERE source = 'api')  AS api_matches,
                   (SELECT COUNT(*) FROM matches WHERE source = 'seed') AS seed_matches,
                   (SELECT COUNT(*) FROM batting_innings) AS batting_rows,
                   (SELECT COUNT(*) FROM bowling_innings) AS bowling_rows,
                   (SELECT MAX(match_date) FROM matches WHERE match_status = 'Completed')
                       AS latest_match
        """) or {}

    # ------------------------------------------------------------- write
    def create(self, match: Match) -> int:
        cols = ", ".join(_MATCH_COLUMNS)
        binds = ", ".join(f":{c}" for c in _MATCH_COLUMNS)
        with self.transaction() as conn:
            return conn.execute(text(f"INSERT INTO matches ({cols}) VALUES ({binds}) "
                                     "RETURNING match_id"), match.to_db()).scalar_one()

    def update(self, match_id: int, match: Match) -> bool:
        sets = ", ".join(f"{c} = :{c}" for c in _EDITABLE)
        params = {c: getattr(match, c) for c in _EDITABLE} | {"id": match_id}
        return self.execute(f"UPDATE matches SET {sets} WHERE match_id = :id", params) == 1

    def delete(self, match_id: int) -> bool:
        """Delete a match; its innings rows are removed by ON DELETE CASCADE."""
        return self.execute("DELETE FROM matches WHERE match_id = :id", {"id": match_id}) == 1

    # ------------------------------------------------------------- API
    @staticmethod
    def upsert_api(conn: Connection, row: dict) -> int:
        """Insert or refresh a match keyed on its Cricbuzz id; returns match_id."""
        row = {c: row.get(c) for c in _MATCH_COLUMNS} | {"source": "api"}
        cols = ", ".join(_MATCH_COLUMNS)
        binds = ", ".join(f":{c}" for c in _MATCH_COLUMNS)
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in _EDITABLE)
        return conn.execute(text(f"""
            INSERT INTO matches ({cols}) VALUES ({binds})
            ON CONFLICT (cricbuzz_match_id) DO UPDATE SET {updates}
            RETURNING match_id
        """), row).scalar_one()
