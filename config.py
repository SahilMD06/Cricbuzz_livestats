"""Central application settings for Cricbuzz LiveStats.

Every other module reads configuration from the ``settings`` object defined
here and never touches ``os.environ`` directly. That keeps the lookup rules
in one place.

Lookup order for each setting:
    1. Streamlit secrets (``st.secrets``)  - used on Streamlit Community Cloud
    2. Environment variables / ``.env``    - used for local development
    3. The default declared below           - only for non-secret values

Usage:
    from config import settings
    settings.require("database_url")   # fail fast with a helpful message
    engine = create_engine(settings.database_url)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

# Values copied from .env.example that mean "not filled in yet".
_PLACEHOLDERS = ("your_rapidapi_key_here", "your_password", "change_me")


class ConfigError(RuntimeError):
    """Raised when a required setting is missing or invalid."""


def _from_streamlit_secrets(name: str) -> str | None:
    """Return a value from st.secrets, or None if unavailable.

    st.secrets raises when no secrets.toml exists or when code runs outside
    Streamlit (e.g. scripts, tests), so any failure simply means "not set".
    """
    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:  # noqa: BLE001 - absence of secrets is not an error
        return None
    return None


def _get(name: str, default: str | None = None) -> str | None:
    """Look a setting up in secrets, then the environment, then the default."""
    value = _from_streamlit_secrets(name) or os.getenv(name)
    return value.strip() if value else default


def _get_int(name: str, default: int) -> int:
    """Read an integer setting, raising ConfigError on a non-numeric value."""
    raw = _get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"Setting '{name}' must be an integer, got '{raw}'.") from exc


def _is_placeholder(value: str | None) -> bool:
    """True if the value is empty or still contains a template placeholder."""
    return not value or any(p in value for p in _PLACEHOLDERS)


@dataclass(frozen=True)
class Settings:
    """Immutable application settings.

    Secrets use ``repr=False`` so printing or logging the object never
    leaks the API key, password or database URL.
    """

    rapidapi_key: str | None = field(repr=False)
    rapidapi_host: str
    api_timeout: int
    database_url: str | None = field(repr=False)
    admin_password: str | None = field(repr=False)
    cache_ttl_live: int
    cache_ttl_stats: int
    log_level: str

    @property
    def api_base_url(self) -> str:
        """Base URL for every Cricbuzz request."""
        return f"https://{self.rapidapi_host}"

    @property
    def has_api_key(self) -> bool:
        """True when a real (non-placeholder) API key is configured."""
        return not _is_placeholder(self.rapidapi_key)

    @property
    def has_database_url(self) -> bool:
        """True when a real (non-placeholder) database URL is configured."""
        return not _is_placeholder(self.database_url)

    def require(self, *names: str) -> None:
        """Raise ConfigError if any named setting is missing or a placeholder.

        Call this at the point of use (DB connection, API client) rather than
        at import time, so e.g. the database scripts still run before an API
        key has been obtained.
        """
        missing = [n for n in names if _is_placeholder(getattr(self, n, None))]
        if missing:
            env_names = ", ".join(n.upper() for n in missing)
            raise ConfigError(
                f"Missing setting(s): {env_names}. "
                "Copy .env.example to .env and fill in real values "
                "(or add them to Streamlit secrets when deployed)."
            )


def load_settings() -> Settings:
    """Build the Settings object from secrets / environment / defaults."""
    return Settings(
        rapidapi_key=_get("RAPIDAPI_KEY"),
        rapidapi_host=_get("RAPIDAPI_HOST", "cricbuzz-cricket.p.rapidapi.com"),
        api_timeout=_get_int("API_TIMEOUT", 15),
        database_url=_get("DATABASE_URL"),
        admin_password=_get("ADMIN_PASSWORD"),
        cache_ttl_live=_get_int("CACHE_TTL_LIVE", 60),
        cache_ttl_stats=_get_int("CACHE_TTL_STATS", 3600),
        log_level=(_get("LOG_LEVEL", "INFO") or "INFO").upper(),
    )


settings = load_settings()
