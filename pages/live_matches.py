"""Live Matches page: ongoing / recent / upcoming matches and scorecards (Cricbuzz API).

API calls are cached (``st.cache_data``) so widget clicks and reruns do not
spend the RapidAPI quota: match lists for 60 s, scorecards for 60 s.
Without an API key the page falls back to the latest matches in the database.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from components.cards import (api_key_missing_notice, match_card, page_header,
                              show_error)
from components.charts import simple_bar
from config import ConfigError, settings
from core.exceptions import AppError
from services.live_service import LiveMatchService
from services.match_service import MatchService

page_header("Cricbuzz API", "Live matches",
            "Ongoing matches with scorecards, batters, bowlers, status and venue.")


@st.cache_data(ttl=settings.cache_ttl_live, show_spinner="Fetching matches …")
def fetch_cards(kind: str):
    return LiveMatchService().cards(kind)


@st.cache_data(ttl=settings.cache_ttl_live, show_spinner="Fetching scorecard …")
def fetch_scorecard(match_id: int):
    return LiveMatchService().scorecard(match_id)


# ---------------------------------------------------------------- helpers
def render_scorecard(match_id: int) -> None:
    """Header + one tab per innings with batting/bowling tables and a chart."""
    try:
        meta, innings = fetch_scorecard(match_id)
    except AppError as exc:
        show_error(exc)
        return
    t1, t2 = meta["team1"]["name"], meta["team2"]["name"]
    st.markdown(f"### {t1} vs {t2}")
    venue = ", ".join(x for x in (meta["venue"]["name"], meta["venue"]["city"]) if x)
    info = [meta["match_description"], meta["match_format"] or "", venue,
            str(meta["match_date"] or "")]
    st.caption(" · ".join(i for i in info if i))
    if meta["status"]:
        st.success(meta["status"])
    if not innings:
        st.info("No scorecard yet – the match may not have started.")
        return
    tabs = st.tabs([f"{i.batting_team or 'Innings'} · {i.runs if i.runs is not None else '-'}"
                    f"/{i.wickets if i.wickets is not None else '-'} ({i.overs or '-'} ov)"
                    for i in innings])
    for tab, inn in zip(tabs, innings):
        with tab:
            bat = pd.DataFrame(inn.batting)
            if not bat.empty:
                bat = bat.rename(columns={"batting_position": "#", "name": "Batter",
                                          "dismissal": "Dismissal", "runs": "R",
                                          "balls_faced": "B", "fours": "4s", "sixes": "6s",
                                          "strike_rate": "SR"})
                st.markdown("**Batting**")
                st.dataframe(bat[["#", "Batter", "Dismissal", "R", "B", "4s", "6s", "SR"]],
                             hide_index=True, width="stretch")
            bowl = pd.DataFrame(inn.bowling)
            if not bowl.empty:
                bowl = bowl.rename(columns={"name": "Bowler", "overs": "O", "maidens": "M",
                                            "runs_conceded": "R", "wickets": "W",
                                            "economy": "Econ"})
                st.markdown(f"**Bowling – {inn.bowling_team}**")
                st.dataframe(bowl[["Bowler", "O", "M", "R", "W", "Econ"]],
                             hide_index=True, width="stretch")
            if not bat.empty:
                simple_bar(bat.sort_values("R", ascending=False).head(11), "Batter", "R",
                           title="Runs by batter")


def render_list(kind: str) -> None:
    """Cards in a two-column grid plus a scorecard picker."""
    try:
        cards = fetch_cards(kind)
    except AppError as exc:
        show_error(exc)
        return
    if not cards:
        st.info({"live": "No matches are live right now – check the Recent tab.",
                 "recent": "No recent matches returned.",
                 "upcoming": "No upcoming matches returned."}[kind])
        return
    formats = sorted({c.match_format for c in cards if c.match_format})
    chosen = st.multiselect("Formats", formats, default=formats, key=f"fmt_{kind}")
    cards = [c for c in cards if c.match_format in chosen] or cards
    grid = st.columns(2)
    for i, card in enumerate(cards[:20]):
        with grid[i % 2]:
            match_card(card)
    if kind != "upcoming":
        labels = {f"{c.team1_short or c.team1} vs {c.team2_short or c.team2} · "
                  f"{c.description}": c.match_id for c in cards}
        pick = st.selectbox("Open full scorecard", ["—"] + list(labels), key=f"pick_{kind}")
        if pick != "—":
            render_scorecard(labels[pick])


def render_database_fallback() -> None:
    """Latest matches stored in the database (when the API is unavailable)."""
    try:
        service = MatchService()
        df = service.search(status="Completed", limit=12)
    except (AppError, ConfigError) as exc:
        show_error(exc)
        return
    st.dataframe(df.drop(columns=["source"]), hide_index=True, width="stretch")
    if not df.empty:
        options = {f"{r.team1_name} vs {r.team2_name} · {r.match_description} · "
                   f"{r.match_date}": r.match_id for r in df.itertuples()}
        pick = st.selectbox("Show stored scorecard", list(options))
        batting, bowling = service.scorecard(options[pick])
        for inn in sorted(batting["innings_no"].unique()) if not batting.empty else []:
            team = batting.loc[batting.innings_no == inn, "team_name"].iloc[0]
            st.markdown(f"**Innings {inn} – {team}**")
            st.dataframe(batting[batting.innings_no == inn]
                         .drop(columns=["innings_no", "team_name"]),
                         hide_index=True, width="stretch")
            st.dataframe(bowling[bowling.innings_no == inn].drop(columns=["innings_no"]),
                         hide_index=True, width="stretch")


# ---------------------------------------------------------------- page body
if not settings.has_api_key:
    api_key_missing_notice()
    render_database_fallback()
    st.stop()

top = st.columns([1, 1, 3])
if top[0].button("Refresh now", icon=":material/refresh:"):
    fetch_cards.clear()
    fetch_scorecard.clear()
auto = top[1].toggle("Auto-refresh (60 s)", value=False,
                     help="Re-fetches the live list every 60 seconds (uses API quota).")

live_tab, recent_tab, upcoming_tab = st.tabs(["Live", "Recent", "Upcoming"])
with live_tab:
    if auto:
        @st.fragment(run_every=60)
        def _auto_live():
            fetch_cards.clear()
            render_list("live")
        _auto_live()
    else:
        render_list("live")
with recent_tab:
    render_list("recent")
with upcoming_tab:
    render_list("upcoming")
