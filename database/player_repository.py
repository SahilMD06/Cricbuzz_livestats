"""PlayerRepository - SQL for ``players`` and ``player_format_stats``."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import Connection, text

from database.base_repository import BaseRepository
from models.entities import Player

_PLAYER_COLUMNS = ("full_name", "team_id", "playing_role", "batting_style", "bowling_style",
                   "date_of_birth", "source", "cricbuzz_player_id")


class PlayerRepository(BaseRepository):
    """CRUD for players plus API upserts and career stats."""

    # ------------------------------------------------------------- read
    def search(self, name: str = "", team_id: int | None = None, role: str | None = None,
               limit: int = 200) -> pd.DataFrame:
        """Filtered player list (all filters optional)."""
        return self.fetch_df("""
            SELECT p.player_id, p.full_name, t.team_name, p.playing_role,
                   p.batting_style, p.bowling_style, p.date_of_birth, p.source,
                   p.updated_at
            FROM players p JOIN teams t ON t.team_id = p.team_id
            WHERE (:name = '' OR p.full_name ILIKE :pattern)
              AND (CAST(:team_id AS INTEGER) IS NULL OR p.team_id = :team_id)
              AND (CAST(:role AS VARCHAR) IS NULL OR p.playing_role = :role)
            ORDER BY p.full_name
            LIMIT :limit
        """, {"name": name.strip(), "pattern": f"%{name.strip()}%", "team_id": team_id,
              "role": role, "limit": limit})

    def get(self, player_id: int) -> Player | None:
        row = self.fetch_one(f"SELECT player_id, {', '.join(_PLAYER_COLUMNS)} "
                             "FROM players WHERE player_id = :id", {"id": player_id})
        return Player(**row) if row else None

    def history_counts(self, player_id: int) -> dict:
        """How many innings/stat rows reference this player (explains blocked deletes)."""
        return self.fetch_one("""
            SELECT (SELECT COUNT(*) FROM batting_innings WHERE player_id = :id) AS batting,
                   (SELECT COUNT(*) FROM bowling_innings WHERE player_id = :id) AS bowling,
                   (SELECT COUNT(*) FROM player_format_stats WHERE player_id = :id) AS career
        """, {"id": player_id}) or {}

    def career_stats(self, player_id: int) -> pd.DataFrame:
        return self.fetch_df("""
            SELECT match_format, matches, innings, runs, highest_score, batting_average,
                   batting_strike_rate, hundreds, fifties, wickets, bowling_average,
                   economy, catches, stumpings
            FROM player_format_stats WHERE player_id = :id
            ORDER BY CASE match_format WHEN 'Test' THEN 1 WHEN 'ODI' THEN 2 ELSE 3 END
        """, {"id": player_id})

    # ------------------------------------------------------------- write
    def create(self, player: Player) -> int:
        cols = ", ".join(_PLAYER_COLUMNS)
        binds = ", ".join(f":{c}" for c in _PLAYER_COLUMNS)
        with self.transaction() as conn:
            return conn.execute(text(f"INSERT INTO players ({cols}) VALUES ({binds}) "
                                     "RETURNING player_id"), player.to_db()).scalar_one()

    def update(self, player_id: int, player: Player) -> bool:
        editable = ("full_name", "team_id", "playing_role", "batting_style",
                    "bowling_style", "date_of_birth")
        sets = ", ".join(f"{c} = :{c}" for c in editable)
        params = {c: getattr(player, c) for c in editable} | {"id": player_id}
        return self.execute(f"UPDATE players SET {sets} WHERE player_id = :id", params) == 1

    def delete(self, player_id: int) -> bool:
        """Delete a player. Career stats cascade; match history blocks the delete."""
        return self.execute("DELETE FROM players WHERE player_id = :id", {"id": player_id}) == 1

    # ------------------------------------------------------------- API
    @staticmethod
    def upsert_api(conn: Connection, cb_id: int, name: str, team_id: int, role: str,
                   batting_style: str | None = None, bowling_style: str | None = None) -> int:
        """Insert or refresh an API player, keyed on the Cricbuzz id."""
        return conn.execute(text("""
            INSERT INTO players (cricbuzz_player_id, full_name, team_id, playing_role,
                                 batting_style, bowling_style, source)
            VALUES (:cb, :name, :team, :role, :bat, :bowl, 'api')
            ON CONFLICT (cricbuzz_player_id) DO UPDATE
               SET full_name     = EXCLUDED.full_name,
                   batting_style = COALESCE(EXCLUDED.batting_style, players.batting_style),
                   bowling_style = COALESCE(EXCLUDED.bowling_style, players.bowling_style)
            RETURNING player_id
        """), {"cb": cb_id, "name": name, "team": team_id, "role": role,
               "bat": batting_style, "bowl": bowling_style}).scalar_one()

    @staticmethod
    def upsert_career(conn: Connection, player_id: int, rows: list[dict]) -> int:
        """Replace a player's per-format career snapshot."""
        cols = ("matches", "innings", "runs", "highest_score", "batting_average",
                "batting_strike_rate", "hundreds", "fifties", "balls_bowled", "wickets",
                "bowling_average", "economy")
        for row in rows:
            params = {c: row.get(c) for c in cols}
            for c in ("matches", "innings", "runs", "hundreds", "fifties",
                      "balls_bowled", "wickets"):
                params[c] = params[c] or 0
            params.update(player_id=player_id, fmt=row["match_format"])
            conn.execute(text(f"""
                INSERT INTO player_format_stats (player_id, match_format, {', '.join(cols)})
                VALUES (:player_id, :fmt, {', '.join(':' + c for c in cols)})
                ON CONFLICT (player_id, match_format) DO UPDATE
                   SET {', '.join(f'{c} = EXCLUDED.{c}' for c in cols)}, last_updated = now()
            """), params)
        return len(rows)
