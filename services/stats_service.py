"""TopStatsService - API leaderboards as DataFrames."""
from __future__ import annotations

import pandas as pd

from api.client import CricbuzzClient
from api.endpoints import TOP_STATS_CATEGORIES
from services import transformers as tf


class TopStatsService:
    """Most runs, most wickets, ... per format, from the Cricbuzz API."""

    def __init__(self, client: CricbuzzClient | None = None) -> None:
        self.client = client or CricbuzzClient()

    @property
    def available(self) -> bool:
        return self.client.is_configured

    @staticmethod
    def categories() -> list[tuple[str, str, str]]:
        return TOP_STATS_CATEGORIES

    def leaderboard(self, stats_type: str, match_format: str,
                    year: int | None = None) -> pd.DataFrame:
        """Leaderboard table; numeric-looking columns are converted to numbers."""
        rows = tf.parse_top_stats(self.client.get_top_stats(stats_type, match_format, year))
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        for col in df.columns:
            if col == "player_id":
                continue
            converted = pd.to_numeric(df[col].astype(str).str.replace(",", "")
                                      .str.replace("*", "", regex=False), errors="coerce")
            if converted.notna().mean() > 0.8:      # mostly numeric -> numeric column
                df[col] = converted
        df.insert(0, "Rank", range(1, len(df) + 1))
        return df
