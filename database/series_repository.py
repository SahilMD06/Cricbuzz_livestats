"""SeriesRepository - SQL for the ``series`` table."""
from __future__ import annotations

from datetime import date

from sqlalchemy import Connection, text

from database.base_repository import BaseRepository


class SeriesRepository(BaseRepository):
    """Read series; upsert series discovered through the API."""

    def list_all(self) -> list[dict]:
        return self.fetch_all(
            "SELECT series_id, series_name, match_type, start_date FROM series "
            "ORDER BY start_date DESC")

    @staticmethod
    def upsert_api(conn: Connection, cb_id: int | None, name: str, match_type: str,
                   start_date: date, host_country: str | None) -> int | None:
        """Insert a series seen in a scorecard, or extend an existing one."""
        if cb_id is None:
            return None
        return conn.execute(text("""
            INSERT INTO series (cricbuzz_series_id, series_name, host_country, match_type,
                                start_date, end_date)
            VALUES (:cb, :name, :host, :mtype, :start, :start)
            ON CONFLICT (cricbuzz_series_id) DO UPDATE
               SET start_date = LEAST(series.start_date, EXCLUDED.start_date),
                   end_date   = GREATEST(series.end_date, EXCLUDED.end_date),
                   match_type = CASE WHEN series.match_type = EXCLUDED.match_type
                                     THEN series.match_type ELSE 'Mixed' END
            RETURNING series_id
        """), {"cb": cb_id, "name": name or f"Series {cb_id}", "host": host_country,
               "mtype": match_type, "start": start_date}).scalar_one()
