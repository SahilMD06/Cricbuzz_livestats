"""CricbuzzClient - the only code in the project that talks HTTP.

Responsibilities:
    * one ``requests.Session`` (connection reuse, headers set once)
    * a timeout on every call (a hung request would freeze the Streamlit page)
    * retries with exponential backoff for transient failures only
      (5xx, timeouts, connection errors, per-second 429s)
    * mapping HTTP failures to the exceptions in ``core.exceptions``
    * tracking the RapidAPI monthly quota from response headers
    * optional "record once, replay forever": save raw JSON to data/raw/

It returns raw JSON (dicts). Turning JSON into rows is the job of
``services.transformers``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests
from tenacity import (retry, retry_if_exception_type, stop_after_attempt,
                      wait_exponential)

from api import endpoints as ep
from config import settings
from core.exceptions import (APIAuthError, APINotFoundError, APIRateLimitError,
                             APIResponseError)
from utils.logger import get_logger

log = get_logger(__name__)


class _TransientError(APIResponseError):
    """Internal marker: this failure is worth retrying."""


class _TransientRateLimit(_TransientError, APIRateLimitError):
    """Per-second rate limit (quota not exhausted) - retry after a pause."""


class CricbuzzClient:
    """Thin, defensive wrapper around the Cricbuzz RapidAPI endpoints."""

    def __init__(self, api_key: str | None = None, host: str | None = None,
                 timeout: int | None = None, raw_dir: Path | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.rapidapi_key
        self.host = host or settings.rapidapi_host
        self.base_url = f"https://{self.host}"
        self.timeout = (5, timeout or settings.api_timeout)  # (connect, read)
        self.raw_dir = raw_dir
        self.quota: dict[str, int | None] = {"limit": None, "remaining": None}
        self.session = requests.Session()
        self.session.headers.update({
            "x-rapidapi-key": self.api_key or "",
            "x-rapidapi-host": self.host,
            "Accept": "application/json",
        })

    # ------------------------------------------------------------------ core
    @property
    def is_configured(self) -> bool:
        """True if a real API key is available."""
        return bool(self.api_key) and "your_rapidapi_key" not in (self.api_key or "")

    def get(self, path: str, params: dict[str, Any] | None = None,
            save_as: str | None = None) -> dict:
        """GET ``path`` and return parsed JSON ({} for an empty 204 response).

        Raises:
            APIAuthError, APINotFoundError, APIRateLimitError, APIResponseError
        """
        if not self.is_configured:
            raise APIAuthError("No Cricbuzz API key configured. Add RAPIDAPI_KEY to .env.")
        try:
            data = self._get_with_retry(path, params)
        except _TransientRateLimit as exc:      # retries exhausted
            raise APIRateLimitError(exc.message, status_code=429) from exc
        except _TransientError as exc:
            raise APIResponseError(exc.message, status_code=exc.status_code,
                                   detail=exc.detail) from exc
        if save_as and self.raw_dir:
            self.raw_dir.mkdir(parents=True, exist_ok=True)
            (self.raw_dir / f"{save_as}.json").write_text(
                json.dumps(data, indent=2), encoding="utf-8")
        return data

    @retry(retry=retry_if_exception_type(_TransientError),
           stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=1, min=1, max=8),
           reraise=True)
    def _get_with_retry(self, path: str, params: dict[str, Any] | None) -> dict:
        url = f"{self.base_url}{path}"
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
        except (requests.Timeout, requests.ConnectionError) as exc:
            log.warning("Network problem calling %s: %s", path, exc)
            raise _TransientError("Could not reach the Cricbuzz API (network/timeout).",
                                  detail=str(exc)) from exc
        self._track_quota(resp)
        return self._handle(resp, path)

    def _track_quota(self, resp: requests.Response) -> None:
        for key, header in (("limit", "x-ratelimit-requests-limit"),
                            ("remaining", "x-ratelimit-requests-remaining")):
            value = resp.headers.get(header)
            if value is not None and value.isdigit():
                self.quota[key] = int(value)
        if self.quota["remaining"] is not None:
            log.info("API quota remaining: %s/%s", self.quota["remaining"],
                     self.quota["limit"])

    def _handle(self, resp: requests.Response, path: str) -> dict:
        """Map the HTTP status to data or to a specific exception."""
        code = resp.status_code
        if code == 204 or (code == 200 and not resp.content):
            return {}
        if code == 200:
            try:
                data = resp.json()
            except ValueError as exc:
                raise APIResponseError("The API returned invalid JSON.", status_code=200,
                                       detail=resp.text[:300]) from exc
            return data if isinstance(data, dict) else {"data": data}
        snippet = resp.text[:300]
        if code in (401, 403):
            raise APIAuthError(
                "The API rejected the key. Check RAPIDAPI_KEY and that you clicked "
                "'Subscribe' on the Cricbuzz Cricket API's free plan.",
                status_code=code, detail=snippet)
        if code == 404:
            raise APINotFoundError(f"Not found: {path}", status_code=code, detail=snippet)
        if code == 429:
            if self.quota["remaining"] == 0:
                raise APIRateLimitError("Monthly API quota used up. Live data is unavailable "
                                        "until it resets.", status_code=code, detail=snippet)
            raise _TransientRateLimit("API rate limit hit; retrying.", status_code=code)
        if code >= 500:
            raise _TransientError(f"Cricbuzz server error ({code}).", status_code=code,
                                  detail=snippet)
        raise APIResponseError(f"Unexpected API response ({code}).", status_code=code,
                               detail=snippet)

    # ------------------------------------------------------------- endpoints
    def get_live_matches(self) -> dict:
        return self.get(ep.LIVE_MATCHES, save_as="live")

    def get_recent_matches(self) -> dict:
        return self.get(ep.RECENT_MATCHES, save_as="recent")

    def get_upcoming_matches(self) -> dict:
        return self.get(ep.UPCOMING_MATCHES, save_as="upcoming")

    def get_match_info(self, match_id: int) -> dict:
        return self.get(ep.MATCH_INFO.format(match_id=match_id), save_as=f"info_{match_id}")

    def get_scorecard(self, match_id: int) -> dict:
        """Full scorecard; falls back to the newer 'hscard' path if needed."""
        try:
            data = self.get(ep.SCORECARD.format(match_id=match_id),
                            save_as=f"scorecard_{match_id}")
            if data:
                return data
        except APINotFoundError:
            log.info("scard not found for %s, trying hscard", match_id)
        return self.get(ep.SCORECARD_ALT.format(match_id=match_id),
                        save_as=f"hscard_{match_id}")

    def get_top_stats_types(self) -> dict:
        return self.get(ep.TOP_STATS_TYPES, save_as="topstats_types")

    def get_top_stats(self, stats_type: str, match_format: str,
                      year: int | None = None) -> dict:
        params: dict[str, Any] = {"statsType": stats_type,
                                  "matchType": ep.MATCH_TYPE_CODES[match_format]}
        if year:
            params["year"] = year
        return self.get(ep.TOP_STATS, params=params,
                        save_as=f"topstats_{stats_type}_{match_format}")

    def search_player(self, name: str) -> dict:
        return self.get(ep.PLAYER_SEARCH, params={"plrN": name})

    def get_player(self, player_id: int) -> dict:
        return self.get(ep.PLAYER_INFO.format(player_id=player_id),
                        save_as=f"player_{player_id}")

    def get_player_batting(self, player_id: int) -> dict:
        return self.get(ep.PLAYER_BATTING.format(player_id=player_id),
                        save_as=f"player_batting_{player_id}")

    def get_player_bowling(self, player_id: int) -> dict:
        return self.get(ep.PLAYER_BOWLING.format(player_id=player_id),
                        save_as=f"player_bowling_{player_id}")

    def get_venue(self, venue_id: int) -> dict:
        return self.get(ep.VENUE_INFO.format(venue_id=venue_id), save_as=f"venue_{venue_id}")

    def get_teams(self) -> dict:
        return self.get(ep.TEAMS_INTERNATIONAL, save_as="teams")

    def get_series_list(self) -> dict:
        return self.get(ep.SERIES_INTERNATIONAL, save_as="series")
