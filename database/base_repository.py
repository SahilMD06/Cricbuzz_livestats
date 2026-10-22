"""BaseRepository - shared plumbing for every repository.

Repositories are the ONLY classes that contain SQL for data manipulation.
They always use bound parameters (``:name``), never f-strings with user
values, which makes SQL injection impossible.

Database errors are translated into the application's own exceptions so
pages can show a friendly message:

    23503 foreign_key_violation -> RecordInUseError
    23505 unique_violation      -> DatabaseError("already exists")
    23514 check_violation       -> ValidationError
    connection problems         -> DatabaseConnectionError
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import pandas as pd
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError, SQLAlchemyError

from core.exceptions import (DatabaseConnectionError, DatabaseError, RecordInUseError,
                             ValidationError)
from utils.db_connection import get_engine
from utils.logger import get_logger

log = get_logger(__name__)


def translate_db_error(exc: Exception) -> Exception:
    """Map a SQLAlchemy/psycopg2 exception to an application exception."""
    orig = getattr(exc, "orig", None)
    code = getattr(orig, "pgcode", None)
    detail = str(orig or exc).strip()
    if isinstance(exc, OperationalError) and code is None:
        return DatabaseConnectionError("Lost connection to the database. Please retry.",
                                       detail=detail)
    if code == "23503":
        return RecordInUseError(
            "This record is referenced by other records (e.g. a player with match "
            "history, or a team with players), so it cannot be deleted.", detail=detail)
    if code == "23505":
        return DatabaseError("A record with the same unique value already exists.",
                             detail=detail)
    if code in ("23514", "23502"):
        constraint = getattr(getattr(orig, "diag", None), "constraint_name", None)
        return ValidationError([f"The database rejected the values "
                                f"(rule: {constraint or 'NOT NULL'})."])
    if isinstance(exc, (IntegrityError, DBAPIError, SQLAlchemyError)):
        return DatabaseError("The database operation failed.", detail=detail)
    return exc


class BaseRepository:
    """Holds the engine and offers small, safe query helpers."""

    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine or get_engine()

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        """``with repo.transaction() as conn:`` - commit on success, rollback on error."""
        try:
            with self.engine.begin() as conn:
                yield conn
        except SQLAlchemyError as exc:
            log.warning("DB error: %s", exc)
            raise translate_db_error(exc) from exc

    def fetch_all(self, sql: str, params: dict[str, Any] | None = None) -> list[dict]:
        """Run a SELECT and return a list of dicts."""
        with self.transaction() as conn:
            return [dict(r) for r in conn.execute(text(sql), params or {}).mappings()]

    def fetch_one(self, sql: str, params: dict[str, Any] | None = None) -> dict | None:
        """Run a SELECT and return the first row as a dict (or None)."""
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

    def fetch_scalar(self, sql: str, params: dict[str, Any] | None = None) -> Any:
        with self.transaction() as conn:
            return conn.execute(text(sql), params or {}).scalar()

    def fetch_df(self, sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
        """Run a SELECT and return a pandas DataFrame."""
        with self.transaction() as conn:
            result = conn.execute(text(sql), params or {})
            return pd.DataFrame(result.fetchall(), columns=list(result.keys()))

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> int:
        """Run INSERT/UPDATE/DELETE in its own transaction; return rows affected."""
        with self.transaction() as conn:
            return conn.execute(text(sql), params or {}).rowcount
