"""Load recent completed international matches from the Cricbuzz API.

Usage (from the project root):
    python -m scripts.ingest                 # up to 5 recent matches
    python -m scripts.ingest --limit 10
    python -m scripts.ingest --match 112345  # one specific Cricbuzz match id
    python -m scripts.ingest --no-venues     # save quota: skip venue lookups

API cost: 1 call for the recent list + 1 per match (+1 per new venue).
"""
from __future__ import annotations

import argparse
import sys

from api.client import CricbuzzClient
from config import ConfigError
from core.exceptions import AppError
from services.ingestion_service import IngestionService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest completed matches from Cricbuzz.")
    parser.add_argument("--limit", type=int, default=5, help="max matches to load")
    parser.add_argument("--match", type=int, help="load one Cricbuzz match id")
    parser.add_argument("--no-venues", action="store_true", help="skip venue detail calls")
    parser.add_argument("--reload", action="store_true", help="reload already-loaded matches")
    args = parser.parse_args(argv)

    try:
        client = CricbuzzClient()
        service = IngestionService(client=client)
        if args.match:
            rows = service.ingest_match(args.match, fetch_venue=not args.no_venues)
            print(f"Loaded match {args.match}: {rows} innings rows.")
        else:
            report = service.ingest_recent(limit=args.limit, skip_loaded=not args.reload,
                                           fetch_venue=not args.no_venues)
            print(f"Ingestion {report.status}: {report.summary()}")
            for line in report.skipped:
                print(f"  skipped  {line}")
            for line in report.failed:
                print(f"  FAILED   {line}")
        if client.quota["remaining"] is not None:
            print(f"API quota remaining: {client.quota['remaining']}/{client.quota['limit']}")
        return 0
    except ValueError as exc:
        print(f"Skipped: {exc}")
        return 1
    except (AppError, ConfigError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
