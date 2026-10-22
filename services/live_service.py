"""LiveMatchService - live/recent/upcoming matches and scorecards for display.

Nothing here is written to the database: live data changes every ball, and
storing half-finished innings would corrupt the analytics. Completed matches
are stored by ``IngestionService`` instead.

Streamlit caching is applied in the page (``st.cache_data``), not here, so
this class stays usable from scripts and tests.
"""
from __future__ import annotations

from api.client import CricbuzzClient
from core.exceptions import APIError
from models.entities import MatchCard, ScorecardInnings
from services import transformers as tf


class LiveMatchService:
    """Fetches match lists and scorecards and converts them for the UI."""

    KINDS = ("live", "recent", "upcoming")

    def __init__(self, client: CricbuzzClient | None = None) -> None:
        self.client = client or CricbuzzClient()

    @property
    def available(self) -> bool:
        return self.client.is_configured

    def cards(self, kind: str = "live") -> list[MatchCard]:
        """Match cards for one list type."""
        fetch = {"live": self.client.get_live_matches,
                 "recent": self.client.get_recent_matches,
                 "upcoming": self.client.get_upcoming_matches}[kind]
        return tf.match_cards(fetch())

    def scorecard(self, match_id: int) -> tuple[dict, list[ScorecardInnings]]:
        """(match meta, innings) for one match; adds match-info only if needed."""
        raw = self.client.get_scorecard(match_id)
        meta = tf.parse_match_meta(raw)
        if not meta["team1"]["name"] or not meta["venue"]["name"]:
            try:
                meta = tf.parse_match_meta(raw, self.client.get_match_info(match_id))
            except APIError:
                pass                                 # show what the scorecard has
        return meta, tf.parse_scorecard(raw, meta)

    def quota(self) -> dict:
        return dict(self.client.quota)
