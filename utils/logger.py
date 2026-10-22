"""Application-wide logging setup.

All modules log through child loggers of one ``cricbuzz`` logger:

    from utils.logger import get_logger
    log = get_logger(__name__)
    log.info("Fetched %d matches", len(matches))

Why not ``print``? Logs carry a timestamp, level and source module, can be
filtered by level (LOG_LEVEL in .env) and are also written to logs/app.log.

Streamlit re-executes scripts on every interaction, so handlers are attached
only once; otherwise every log line would be printed N times.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from config import PROJECT_ROOT, settings

APP_LOGGER_NAME = "cricbuzz"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _configure_app_logger() -> logging.Logger:
    """Attach console and rotating-file handlers to the app logger, once."""
    app_logger = logging.getLogger(APP_LOGGER_NAME)
    if app_logger.handlers:  # already configured (e.g. Streamlit rerun)
        return app_logger

    app_logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
    app_logger.propagate = False  # don't duplicate into the root logger
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    app_logger.addHandler(console)

    try:
        LOG_DIR.mkdir(exist_ok=True)
        file_handler = RotatingFileHandler(
            LOG_DIR / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        app_logger.addHandler(file_handler)
    except OSError:
        # Read-only file systems (some cloud hosts): console logging still works.
        app_logger.warning("File logging disabled: cannot write to %s", LOG_DIR)

    return app_logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger, e.g. get_logger(__name__) -> 'cricbuzz.api.client'."""
    _configure_app_logger()
    return logging.getLogger(f"{APP_LOGGER_NAME}.{name}")
