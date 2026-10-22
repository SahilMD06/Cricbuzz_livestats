"""Centralised database connection handling (required by the project brief).

This is the ONLY module that creates a SQLAlchemy engine. Everything else
imports ``get_engine()``:

    from utils.db_connection import get_engine
    with get_engine().begin() as conn:          # commits, or rolls back on error
        conn.execute(text("SELECT 1"))

Why an engine and not a single connection?
    The engine owns a *pool* of connections. Each ``with engine.begin()``
    borrows one, and returns it when the block ends. Creating a new engine
    per page/rerun would open a new pool every time and eventually exhaust
    the database's connection limit.

Why ``lru_cache`` and not ``st.cache_resource``?
    ``lru_cache`` works everywhere (Streamlit, scripts, tests). Python only
    imports a module once per process, so Streamlit reruns reuse the same
    cached engine.
"""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from config import settings
from core.exceptions import DatabaseConnectionError, DatabaseError
from utils.logger import get_logger

log = get_logger(__name__)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create (once) and return the application's SQLAlchemy engine.

    Pool settings:
        pool_pre_ping  - test a pooled connection before using it; hosted
                         databases (Neon) close idle connections, and this
                         transparently replaces dead ones.
        pool_recycle   - proactively replace connections older than 5 min.
        pool_size / max_overflow - small pool; Streamlit apps are low traffic
                         and free-tier databases limit total connections.

    Raises:
        ConfigError: if DATABASE_URL is missing or still a placeholder.
    """
    settings.require("database_url")
    url = make_url(settings.database_url)
    log.info("Creating database engine for %s@%s/%s",
             url.username, url.host, url.database)  # never log the password
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=5,
        connect_args={"connect_timeout": 10},
    )


def check_connection() -> str:
    """Run a trivial query and return the server version string.

    Raises:
        DatabaseConnectionError: if the database cannot be reached.
        DatabaseError: for any other database failure.
    """
    try:
        with get_engine().connect() as conn:
            return conn.execute(text("SELECT version()")).scalar_one()
    except OperationalError as exc:
        raise DatabaseConnectionError(
            "Could not connect to the database. Check DATABASE_URL in .env "
            "and your internet connection.",
            detail=str(exc.orig),
        ) from exc
    except SQLAlchemyError as exc:
        raise DatabaseError("Database check failed.", detail=str(exc)) from exc


def dispose_engine() -> None:
    """Close all pooled connections and forget the cached engine.

    Useful in tests, or after changing DATABASE_URL at runtime.
    """
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_engine.cache_clear()
