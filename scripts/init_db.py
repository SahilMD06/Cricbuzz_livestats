"""Create the database schema (tables, constraints, indexes, trigger, views).

Usage (from the project root, virtual environment active):

    python -m scripts.init_db            # create anything missing (safe to re-run)
    python -m scripts.init_db --reset    # DROP everything, then recreate (asks first)
    python -m scripts.init_db --reset --yes   # same, no prompt (for scripts/CI)

Why run whole .sql files through the raw DBAPI cursor?
    schema.sql contains a PL/pgSQL function whose body has its own semicolons,
    so naively splitting the file on ';' would break it. psycopg2 can execute
    a multi-statement string in one call, and with no parameters it does not
    treat '%' (used in schema.sql for modulo) as a placeholder.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import text

from config import PROJECT_ROOT, ConfigError
from core.exceptions import AppError
from utils.db_connection import check_connection, get_engine
from utils.logger import get_logger

log = get_logger(__name__)

SQL_DIR: Path = PROJECT_ROOT / "sql"
SQL_FILES: tuple[str, ...] = ("schema.sql", "views.sql")

# Child tables first, so DROP order never violates a foreign key.
ALL_TABLES: tuple[str, ...] = (
    "batting_innings", "bowling_innings", "player_format_stats", "matches",
    "series", "players", "venues", "teams", "ingestion_log",
)
ALL_VIEWS: tuple[str, ...] = (
    "v_match_summary", "v_batting_detail", "v_bowling_detail", "v_player_profile",
)


def run_sql_file(path: Path) -> None:
    """Execute every statement in one .sql file inside a single transaction.

    If any statement fails, the whole file is rolled back, so the database is
    never left half-created.
    """
    sql = path.read_text(encoding="utf-8")
    raw = get_engine().raw_connection()
    try:
        with raw.cursor() as cur:
            cur.execute(sql)
        raw.commit()
        log.info("Executed %s", path.name)
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


def drop_everything() -> None:
    """Drop all project views and tables (and their data)."""
    with get_engine().begin() as conn:
        for view in ALL_VIEWS:
            conn.execute(text(f"DROP VIEW IF EXISTS {view} CASCADE"))
        for table in ALL_TABLES:
            conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        conn.execute(text("DROP FUNCTION IF EXISTS set_updated_at() CASCADE"))
    log.warning("Dropped all tables and views")


def summarise() -> list[tuple[str, int]]:
    """Return (table_name, row_count) for every project table that exists."""
    with get_engine().connect() as conn:
        existing = set(conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        )).scalars())
        return [
            (t, conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar_one())
            for t in reversed(ALL_TABLES) if t in existing
        ]


def confirm(prompt: str) -> bool:
    """Ask a yes/no question on the terminal."""
    return input(f"{prompt} [type 'yes' to continue]: ").strip().lower() == "yes"


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code (0 = success)."""
    parser = argparse.ArgumentParser(description="Create the Cricbuzz LiveStats schema.")
    parser.add_argument("--reset", action="store_true",
                        help="drop all tables and views first (DELETES ALL DATA)")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args(argv)

    try:
        version = check_connection()
        print(f"Connected: {version.split(',')[0]}")

        if args.reset:
            if not args.yes and not confirm("This deletes ALL project data."):
                print("Cancelled.")
                return 1
            drop_everything()

        for name in SQL_FILES:
            run_sql_file(SQL_DIR / name)

        print("\nTables:")
        for table, rows in summarise():
            print(f"  {table:<22} {rows:>7} rows")
        print(f"Views:  {', '.join(ALL_VIEWS)}")
        print("\nSchema ready.")
        return 0

    except (AppError, ConfigError) as exc:
        log.error("%s | %s", exc, getattr(exc, "detail", None) or "")
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
