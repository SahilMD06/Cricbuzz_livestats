"""Home page: project overview, tools, navigation, data freshness, documentation."""
from __future__ import annotations

import streamlit as st

from config import PROJECT_ROOT, ConfigError, settings
from core.exceptions import AppError
from components.cards import page_header, show_error
from database import IngestionLogRepository
from services.match_service import MatchService

page_header("Cricbuzz LiveStats", "Real-time cricket insights & SQL analytics",
            "Live data from the Cricbuzz API, stored in PostgreSQL, analysed with 25 SQL "
            "queries and managed through a full CRUD interface.")


@st.cache_data(ttl=120, show_spinner=False)
def _summary() -> dict:
    return MatchService().summary()


@st.cache_data(ttl=120, show_spinner=False)
def _ingestion_log():
    return IngestionLogRepository().recent(8)


# ---------------------------------------------------------------- status
try:
    s = _summary()
    c = st.columns(5)
    c[0].metric("Matches", f"{s['matches']:,}")
    c[1].metric("Players", f"{s['players']:,}")
    c[2].metric("Teams", s["teams"])
    c[3].metric("Venues", s["venues"])
    c[4].metric("Innings rows", f"{s['batting_rows'] + s['bowling_rows']:,}")
    st.caption(f"Data sources: {s['api_matches']} matches imported from the Cricbuzz API, "
               f"{s['seed_matches']} from the labelled seed dataset. Latest completed match: "
               f"{s['latest_match'] or '—'}.")
    db_ok = True
except (AppError, ConfigError) as exc:
    db_ok = False
    show_error(exc)

api_ok = settings.has_api_key
st.markdown(
    f"**Database:** {'🟢 connected' if db_ok else '🔴 not connected'} &nbsp;·&nbsp; "
    f"**Cricbuzz API key:** {'🟢 configured' if api_ok else '🟠 not configured'}")

st.divider()

# ---------------------------------------------------------------- navigation
st.subheader("What you can do here")
cols = st.columns(2)
with cols[0]:
    st.page_link("pages/live_matches.py", label="Live Matches", icon=":material/sports_cricket:")
    st.caption("Ongoing, recent and upcoming matches with full scorecards from the Cricbuzz API.")
    st.page_link("pages/top_stats.py", label="Top Player Stats", icon=":material/leaderboard:")
    st.caption("Leaderboards: most runs, highest scores, most wickets, best economy …")
with cols[1]:
    st.page_link("pages/sql_queries.py", label="SQL Analytics", icon=":material/query_stats:")
    st.caption("25 SQL questions from beginner to advanced, each with a table, chart and its SQL.")
    st.page_link("pages/crud_operations.py", label="CRUD Operations", icon=":material/edit_note:")
    st.caption("Create, read, update and delete players and matches through validated forms.")

st.divider()

# ---------------------------------------------------------------- about
left, right = st.columns([3, 2])
with left:
    st.subheader("How it works")
    st.markdown("""
1. **API layer** – `api/client.py` calls the Cricbuzz API (RapidAPI) with timeouts,
   retries and quota tracking.
2. **Transform** – `services/transformers.py` turns nested JSON into clean rows
   (pure functions, unit-tested).
3. **Load** – `services/ingestion_service.py` writes each completed match in one
   transaction (teams, venue, match, players, innings).
4. **Analyse** – `sql/queries/` holds the 25 queries; `analytics/` runs them.
5. **Present** – this Streamlit app; live pages are cached to protect the API quota.
""")
    st.subheader("About the data")
    st.markdown("""
The free API quota cannot backfill years of scorecards, so the database also contains a
**deterministic seed dataset** (`scripts/seed_data.py`): fictional players, real grounds,
simulated 2021–today tours. Every seed row is marked `source = 'seed'`; API rows are
marked `source = 'api'`. Live and Top Stats pages always show real API data.
""")
with right:
    st.subheader("Tools used")
    st.markdown("""
| Area | Tool |
|---|---|
| Language | Python 3.10+ |
| Web app | Streamlit |
| Database | PostgreSQL (Neon) |
| DB access | SQLAlchemy 2 + psycopg2 |
| API | Cricbuzz via RapidAPI, `requests` |
| Data | pandas |
| Charts | Plotly |
| Tests | pytest |
""")

st.subheader("Recent data loads")
try:
    log = _ingestion_log()
    if log.empty:
        st.caption("No data loads recorded yet.")
    else:
        st.dataframe(log, hide_index=True, width="stretch")
except (AppError, ConfigError):
    st.caption("Unavailable until the database is connected.")

# ---------------------------------------------------------------- documentation
st.subheader("Documentation")
with st.expander("README – setup, configuration and deployment"):
    readme = PROJECT_ROOT / "README.md"
    st.markdown(readme.read_text(encoding="utf-8") if readme.exists() else "README not found.")
with st.expander("Project folder structure"):
    st.code("""cricbuzz_livestats/
├── app.py                  # entry point + navigation
├── config.py               # settings from .env / st.secrets
├── pages/                  # home, live_matches, top_stats, sql_queries, crud_operations
├── components/             # shared UI widgets and charts
├── api/                    # Cricbuzz HTTP client + endpoint constants
├── services/               # transformers, live/stats/ingestion, CRUD rules
├── database/               # repositories (all CRUD SQL)
├── analytics/              # query registry + runner
├── models/                 # dataclasses
├── core/                   # exception hierarchy
├── utils/                  # db_connection.py, logger, validators, formatters
├── sql/                    # schema.sql, views.sql, queries/q01..q25.sql
├── scripts/                # init_db, seed_data, ingest, api_probe
├── notebooks/              # data_fetching.ipynb
├── tests/                  # unit + integration tests, JSON fixtures
└── documentation/          # requirements checklist, screenshots""", language="text")
