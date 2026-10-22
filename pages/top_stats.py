"""Top Player Stats page: Cricbuzz leaderboards (most runs, wickets, ...).

Leaderboards change slowly, so each one is cached for an hour
(``CACHE_TTL_STATS``). Without an API key the page shows the same kind of
leaderboards computed from the database.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from components.cards import api_key_missing_notice, page_header, show_error
from components.charts import simple_bar
from config import ConfigError, settings
from core.exceptions import AppError
from database import BaseRepository
from services.stats_service import TopStatsService

page_header("Cricbuzz API", "Top player stats",
            "Batting and bowling leaderboards by format.")

# Preferred column to chart for each stat (first match wins).
CHART_COLUMN = {
    "mostRuns": ("Runs", "R"), "highestScore": ("HS", "Score", "Runs", "R"),
    "highestAvg": ("Avg", "Average"), "highestSr": ("SR", "Strike Rate"),
    "mostHundreds": ("100s", "Hundreds"), "mostFifties": ("50s", "Fifties"),
    "mostSixes": ("6s", "Sixes"), "mostFours": ("4s", "Fours"),
    "mostWickets": ("Wkts", "W", "Wickets"), "lowestAvg": ("Avg", "Average"),
    "lowestEcon": ("Eco", "Econ", "Economy"), "mostFiveWickets": ("5w", "5W", "5 Wkts"),
}


@st.cache_data(ttl=settings.cache_ttl_stats, show_spinner="Fetching leaderboard …")
def fetch_leaderboard(stats_type: str, match_format: str, year: int | None) -> pd.DataFrame:
    return TopStatsService().leaderboard(stats_type, match_format, year)


@st.cache_data(ttl=300, show_spinner=False)
def db_leaderboard(metric: str, match_format: str) -> pd.DataFrame:
    """Fallback leaderboards from player_format_stats (column names are fixed)."""
    order = {"runs": "s.runs DESC", "wickets": "s.wickets DESC",
             "average": "s.batting_average DESC NULLS LAST",
             "economy": "s.economy ASC NULLS LAST"}[metric]
    extra = "AND s.balls_bowled >= 600" if metric == "economy" else (
        "AND s.innings >= 20" if metric == "average" else "")
    return BaseRepository().fetch_df(f"""
        SELECT p.full_name AS player, t.short_name AS team, s.matches, s.runs,
               s.batting_average AS average, s.hundreds, s.wickets, s.economy
        FROM player_format_stats s
        JOIN players p ON p.player_id = s.player_id
        JOIN teams t   ON t.team_id   = p.team_id
        WHERE s.match_format = :fmt {extra}
        ORDER BY {order} LIMIT 15""", {"fmt": match_format})


controls = st.columns([1.3, 2, 1])
fmt = controls[0].segmented_control("Format", ["Test", "ODI", "T20I"], default="ODI") or "ODI"

if not settings.has_api_key:
    api_key_missing_notice()
    metric = controls[1].selectbox("Leaderboard", ["runs", "wickets", "average", "economy"],
                                   format_func=lambda m: {"runs": "Most runs",
                                                          "wickets": "Most wickets",
                                                          "average": "Best batting average",
                                                          "economy": "Best economy"}[m])
    try:
        df = db_leaderboard(metric, fmt)
        keep = ["player", "team", "matches"] + (
            ["runs", "average", "hundreds"] if metric in ("runs", "average")
            else ["wickets", "economy"])
        df = df[keep]
        df.insert(0, "rank", range(1, len(df) + 1))
        st.dataframe(df, hide_index=True, width="stretch")
        simple_bar(df, "player", metric, title=f"{fmt} – {metric}")
    except (AppError, ConfigError) as exc:
        show_error(exc)
    st.stop()

categories = TopStatsService.categories()
labels = {f"{label} ({kind})": value for value, label, kind in categories}
choice = controls[1].selectbox("Leaderboard", list(labels))
year_text = controls[2].text_input("Year (optional)", placeholder="e.g. 2025")
year = int(year_text) if year_text.strip().isdigit() else None
stats_type = labels[choice]

try:
    df = fetch_leaderboard(stats_type, fmt, year)
except AppError as exc:
    show_error(exc)
    st.stop()

if df.empty:
    st.info("The API returned no rows for this combination.")
    st.stop()

visible = df.drop(columns=["player_id"], errors="ignore")
st.dataframe(visible, hide_index=True, width="stretch")

name_col = next((c for c in visible.columns
                 if c != "Rank" and not pd.api.types.is_numeric_dtype(visible[c])), None)
numeric = [c for c in visible.columns if c != "Rank"
           and pd.api.types.is_numeric_dtype(visible[c])]
value_col = next((c for c in CHART_COLUMN.get(stats_type, ()) if c in numeric),
                 numeric[-1] if numeric else None)
if name_col and value_col:
    simple_bar(visible.head(15), name_col, value_col, title=f"{choice} · {fmt}")
st.download_button("Download CSV", visible.to_csv(index=False).encode(),
                   file_name=f"{stats_type}_{fmt}.csv", mime="text/csv")
