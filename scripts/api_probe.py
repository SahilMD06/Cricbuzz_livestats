"""One-time exploration of the Cricbuzz API.

Saves raw responses to data/raw/ so parsers can be checked offline and reused
as test fixtures. Uses about 6 API calls.

Usage (from the project root):
    python -m scripts.api_probe
"""
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

HOST = os.getenv("RAPIDAPI_HOST", "cricbuzz-cricket.p.rapidapi.com")
HEADERS = {"x-rapidapi-key": os.environ["RAPIDAPI_KEY"], "x-rapidapi-host": HOST}
RAW_DIR = PROJECT_ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def probe(name: str, path: str) -> dict:
    """GET one endpoint, save the JSON, print status, quota and top-level keys."""
    resp = requests.get(f"https://{HOST}{path}", headers=HEADERS, timeout=(5, 15))
    remaining = resp.headers.get("x-ratelimit-requests-remaining", "?")
    print(f"{name:<16} {resp.status_code}  quota left: {remaining}")
    if resp.status_code != 200 or not resp.content:
        return {}
    data = resp.json()
    (RAW_DIR / f"{name}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"{'':<16} keys: {list(data)[:8]}")
    return data


def first_match_id(payload: dict) -> int:
    """Return the first real (non-advert) matchId from a matches list payload."""
    for type_block in payload.get("typeMatches", payload.get("typematches", [])):
        for series in type_block.get("seriesMatches", type_block.get("seriesmatches", [])):
            wrapper = series.get("seriesAdWrapper") or series.get("seriesadwrapper")
            if wrapper and wrapper.get("matches"):
                info = wrapper["matches"][0].get("matchInfo") or wrapper["matches"][0].get(
                    "matchinfo")
                return info.get("matchId") or info.get("matchid")
    raise ValueError("No matches found in payload")


if __name__ == "__main__":
    recent = probe("recent", "/matches/v1/recent")
    match_id = first_match_id(recent)
    probe("live", "/matches/v1/live")
    probe("scorecard", f"/mcenter/v1/{match_id}/scard")
    probe("player", "/stats/v1/player/1413")
    probe("player_batting", "/stats/v1/player/1413/batting")
    probe("topstats_runs", "/stats/v1/topstats/0?statsType=mostRuns&matchType=2")
