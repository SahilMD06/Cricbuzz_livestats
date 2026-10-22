"""IngestionLogRepository - SQL for the ``ingestion_log`` table."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from database.base_repository import BaseRepository


class IngestionLogRepository(BaseRepository):
    """Records each data load so the Home page can show data freshness."""

    def start(self, source: str, endpoint: str) -> int:
        with self.transaction() as conn:
            return conn.execute(text(
                "INSERT INTO ingestion_log (source, endpoint, status) "
                "VALUES (:s, :e, 'partial') RETURNING log_id"),
                {"s": source, "e": endpoint}).scalar_one()

    def finish(self, log_id: int, records: int, status: str, message: str = "") -> None:
        self.execute(
            "UPDATE ingestion_log SET records = :r, status = :st, message = :m, "
            "finished_at = now() WHERE log_id = :id",
            {"r": records, "st": status, "m": message[:2000], "id": log_id})

    def recent(self, limit: int = 10) -> pd.DataFrame:
        return self.fetch_df(
            "SELECT started_at, source, endpoint, records, status, message "
            "FROM ingestion_log ORDER BY started_at DESC LIMIT :n", {"n": limit})
