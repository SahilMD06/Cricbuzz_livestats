"""InningsRepository - SQL for ``batting_innings`` and ``bowling_innings``."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import Connection, text

from database.base_repository import BaseRepository

_BAT_COLS = ("match_id", "player_id", "team_id", "innings_no", "batting_position", "runs",
             "balls_faced", "fours", "sixes", "is_out", "dismissal")
_BOWL_COLS = ("match_id", "player_id", "team_id", "innings_no", "balls_bowled", "maidens",
              "runs_conceded", "wickets")


class InningsRepository(BaseRepository):
    """Per-innings batting/bowling rows."""

    def scorecard(self, match_id: int) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Batting and bowling tables for one stored match."""
        batting = self.fetch_df("""
            SELECT innings_no, team_name, batting_position AS pos, player_name AS batter,
                   dismissal, runs, balls_faced AS balls, fours, sixes, strike_rate
            FROM v_batting_detail WHERE match_id = :id
            ORDER BY innings_no, batting_position
        """, {"id": match_id})
        bowling = self.fetch_df("""
            SELECT innings_no, team_name, player_name AS bowler, overs, maidens,
                   runs_conceded AS runs, wickets, economy
            FROM v_bowling_detail WHERE match_id = :id
            ORDER BY innings_no, bowling_id
        """, {"id": match_id})
        return batting, bowling

    @staticmethod
    def replace_for_match(conn: Connection, match_id: int, batting: list[dict],
                          bowling: list[dict]) -> tuple[int, int]:
        """Delete then re-insert all innings rows of a match (idempotent reload).

        Runs inside the caller's transaction, so a failure leaves the previous
        rows intact.
        """
        conn.execute(text("DELETE FROM batting_innings WHERE match_id = :id"), {"id": match_id})
        conn.execute(text("DELETE FROM bowling_innings WHERE match_id = :id"), {"id": match_id})
        if batting:
            conn.execute(text(
                f"INSERT INTO batting_innings ({', '.join(_BAT_COLS)}) "
                f"VALUES ({', '.join(':' + c for c in _BAT_COLS)})"),
                [{c: r.get(c) for c in _BAT_COLS} | {"match_id": match_id} for r in batting])
        if bowling:
            conn.execute(text(
                f"INSERT INTO bowling_innings ({', '.join(_BOWL_COLS)}) "
                f"VALUES ({', '.join(':' + c for c in _BOWL_COLS)})"),
                [{c: r.get(c) for c in _BOWL_COLS} | {"match_id": match_id} for r in bowling])
        return len(batting), len(bowling)
