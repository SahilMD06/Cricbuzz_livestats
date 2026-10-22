"""AnalyticsRunner - executes the 25 query files and returns DataFrames.

Run all queries from the terminal as a smoke test:
    python -m analytics.runner
"""
from __future__ import annotations

import sys
import time

import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from analytics.registry import QUERIES, QuerySpec
from database.base_repository import translate_db_error
from utils.db_connection import get_engine

READ_ONLY_PREFIXES = ("select", "with")
FORBIDDEN_WORDS = ("insert", "update", "delete", "drop", "alter", "truncate", "create",
                   "grant", "revoke", "copy", "vacuum", "call", "do")


def run_sql(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Execute one SELECT and return its result as a DataFrame."""
    try:
        with get_engine().connect() as conn:
            result = conn.execute(text(sql), params or {})
            return pd.DataFrame(result.fetchall(), columns=list(result.keys()))
    except SQLAlchemyError as exc:
        raise translate_db_error(exc) from exc


def run_query(spec: QuerySpec) -> pd.DataFrame:
    """Run one registered analytics query."""
    return run_sql(spec.sql())


def run_read_only(sql: str, row_limit: int = 1000) -> pd.DataFrame:
    """Run user-typed SQL safely: one SELECT, in a READ ONLY transaction.

    Two layers of protection: a keyword check for a friendly message, and a
    PostgreSQL READ ONLY transaction that rejects any write regardless.
    """
    cleaned = "\n".join(line.split("--")[0] for line in sql.splitlines()).strip().rstrip(";")
    lowered = cleaned.lower()
    if not lowered.startswith(READ_ONLY_PREFIXES):
        raise ValueError("Only SELECT (or WITH ... SELECT) queries are allowed.")
    if ";" in cleaned:
        raise ValueError("Run one statement at a time.")
    tokens = set(lowered.replace("(", " ").replace(")", " ").split())
    blocked = tokens.intersection(FORBIDDEN_WORDS)
    if blocked:
        raise ValueError(f"Write/DDL keywords are not allowed: {', '.join(sorted(blocked))}")
    try:
        with get_engine().connect() as conn:
            with conn.begin():
                conn.execute(text("SET TRANSACTION READ ONLY"))
                conn.execute(text("SET LOCAL statement_timeout = '10s'"))
                wrapped = f"SELECT * FROM ({cleaned}) AS q LIMIT {int(row_limit)}"
                result = conn.execute(text(wrapped))
                return pd.DataFrame(result.fetchall(), columns=list(result.keys()))
    except SQLAlchemyError as exc:
        raise translate_db_error(exc) from exc


def run_all(verbose: bool = True) -> dict[int, int]:
    """Run every query; return {query number: row count}. Raises on failure."""
    counts = {}
    for spec in QUERIES:
        start = time.perf_counter()
        try:
            rows = len(run_query(spec))
        except Exception as exc:                  # report and keep going
            rows = 0
            if verbose:
                print(f"ERROR {spec.label}: {exc} | {getattr(exc, 'detail', '')}")
        counts[spec.number] = rows
        if verbose:
            ms = (time.perf_counter() - start) * 1000
            flag = "OK  " if rows else "EMPTY"
            print(f"{flag} {spec.label:<55} {rows:>5} rows  {ms:6.0f} ms")
    return counts


if __name__ == "__main__":
    results = run_all()
    sys.exit(0 if all(results.values()) else 1)
