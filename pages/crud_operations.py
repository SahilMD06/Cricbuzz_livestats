"""CRUD page: create, read, update and delete players and matches.

Reading is open to everyone. Writing (add / edit / delete / import) requires
the admin password from ADMIN_PASSWORD, so a public deployment cannot be
wiped by a visitor. Forms use ``st.form`` so the app reruns once per submit,
not on every keystroke.
"""
from __future__ import annotations

import hmac
from datetime import date

import streamlit as st

from components.cards import page_header, show_error
from config import ConfigError, settings
from core.exceptions import AppError
from models.entities import (BATTING_STYLES, BOWLING_STYLES, MATCH_FORMATS,
                             MATCH_STATUSES, PLAYING_ROLES)
from services.match_service import MatchService
from services.player_service import PlayerService

page_header("SQL Database", "CRUD operations",
            "Manage players and matches. Every change is validated, then saved in a "
            "transaction.")

try:
    players = PlayerService()
    matches = MatchService()
    TEAMS = players.list_teams()
    VENUES = matches.list_venues()
    SERIES = matches.list_series()
except (AppError, ConfigError) as exc:
    show_error(exc)
    st.stop()

TEAM_NAMES = {t["team_id"]: t["team_name"] for t in TEAMS}
VENUE_NAMES = {v["venue_id"]: f"{v['venue_name']}, {v['city']}" for v in VENUES}
SERIES_NAMES = {s["series_id"]: s["series_name"] for s in SERIES}


# ---------------------------------------------------------------- admin gate
def is_admin() -> bool:
    return st.session_state.get("is_admin", False)


with st.sidebar:
    st.markdown("**Admin access**")
    if is_admin():
        st.success("Write access enabled")
        if st.button("Log out"):
            st.session_state.is_admin = False
            st.rerun()
    else:
        pwd = st.text_input("Admin password", type="password",
                            help="Set ADMIN_PASSWORD in .env. Default: change_me")
        if st.button("Unlock editing"):
            expected = settings.admin_password or "change_me"
            # compare_digest avoids leaking the password through timing differences
            if hmac.compare_digest(pwd.encode(), expected.encode()):
                st.session_state.is_admin = True
                st.rerun()
            else:
                st.error("Wrong password.")


def require_admin() -> bool:
    if not is_admin():
        st.info("Viewing is open to everyone. Unlock editing in the sidebar to add, "
                "change or delete records.", icon=":material/lock:")
        return False
    return True


def saved(message: str) -> None:
    """After any write: clear cached query results so every page sees the change."""
    st.cache_data.clear()
    st.toast(message, icon="✅")


def _index(options: list, value) -> int:
    return options.index(value) if value in options else 0


# ---------------------------------------------------------------- player form
def player_form(key: str, current=None) -> dict | None:
    """Render the player form; return the submitted values or None."""
    team_ids = list(TEAM_NAMES)
    with st.form(key, clear_on_submit=current is None):
        c1, c2 = st.columns(2)
        name = c1.text_input("Full name *", value=current.full_name if current else "")
        team = c2.selectbox("Team *", team_ids, format_func=TEAM_NAMES.get,
                            index=_index(team_ids, current.team_id if current else None))
        role = c1.selectbox("Playing role *", PLAYING_ROLES,
                            index=_index(list(PLAYING_ROLES),
                                         current.playing_role if current else None))
        bat_opts = ["—", *BATTING_STYLES]
        bat = c2.selectbox("Batting style", bat_opts,
                           index=_index(bat_opts, current.batting_style if current else "—"))
        bowl_opts = ["Does not bowl", *BOWLING_STYLES]
        cur_bowl = (current.bowling_style or "Does not bowl") if current else "Does not bowl"
        if cur_bowl not in bowl_opts:
            bowl_opts.append(cur_bowl)
        bowl = c1.selectbox("Bowling style", bowl_opts, index=_index(bowl_opts, cur_bowl))
        dob = c2.date_input("Date of birth", value=current.date_of_birth if current else None,
                            min_value=date(1950, 1, 1), max_value=date.today())
        if st.form_submit_button("Save player", type="primary"):
            return {"full_name": name, "team_id": team, "playing_role": role,
                    "batting_style": None if bat == "—" else bat,
                    "bowling_style": None if bowl == "Does not bowl" else bowl,
                    "date_of_birth": dob}
    return None


def pick_player(key: str):
    """Search box + select; returns (player_id, label) or (None, None)."""
    term = st.text_input("Search player by name", key=f"{key}_term")
    df = players.search(name=term, limit=100)
    if df.empty:
        st.caption("No players match.")
        return None, None
    options = {f"{r.full_name} · {r.team_name} · {r.playing_role} (#{r.player_id})":
               r.player_id for r in df.itertuples()}
    label = st.selectbox("Player", list(options), key=f"{key}_sel")
    return options[label], label


# ---------------------------------------------------------------- match form
def match_form(key: str, current=None) -> dict | None:
    """Render the match form; return submitted values or None."""
    team_ids, venue_ids = list(TEAM_NAMES), list(VENUE_NAMES)
    series_ids = [None, *SERIES_NAMES]
    with st.form(key, clear_on_submit=current is None):
        c1, c2, c3 = st.columns(3)
        desc = c1.text_input("Description *", value=current.match_description if current
                             else "", placeholder="e.g. 2nd ODI")
        fmt = c2.selectbox("Format *", MATCH_FORMATS,
                           index=_index(list(MATCH_FORMATS),
                                        current.match_format if current else None))
        mdate = c3.date_input("Match date *", value=current.match_date if current
                              else date.today())
        team1 = c1.selectbox("Team 1 *", team_ids, format_func=TEAM_NAMES.get,
                             index=_index(team_ids, current.team1_id if current else None))
        team2 = c2.selectbox("Team 2 *", team_ids, format_func=TEAM_NAMES.get,
                             index=_index(team_ids, current.team2_id if current
                                          else (team_ids[1] if len(team_ids) > 1 else None)))
        venue = c3.selectbox("Venue *", venue_ids, format_func=VENUE_NAMES.get,
                             index=_index(venue_ids, current.venue_id if current else None))
        series = c1.selectbox("Series", series_ids,
                              format_func=lambda s: "— none —" if s is None
                              else SERIES_NAMES[s],
                              index=_index(series_ids, current.series_id if current else None))
        status = c2.selectbox("Status *", MATCH_STATUSES,
                              index=_index(list(MATCH_STATUSES),
                                           current.match_status if current else "Completed"))
        st.markdown("**Toss and result** – leave the toss empty if unknown; results apply "
                    "to completed matches only.")
        d1, d2, d3, d4, d5 = st.columns(5)
        toss_opts = [None, *team_ids]
        toss = d1.selectbox("Toss winner", toss_opts,
                            format_func=lambda t: "—" if t is None else TEAM_NAMES[t],
                            index=_index(toss_opts, current.toss_winner_id if current else None))
        decision = d2.selectbox("Decision", ["bat", "bowl"],
                                index=_index(["bat", "bowl"],
                                             current.toss_decision if current else "bat"))
        vtypes = ["runs", "wickets", "innings", "tie", "draw", "no result"]
        vtype = d3.selectbox("Result type", vtypes,
                             index=_index(vtypes, current.victory_type if current else "runs"))
        winner_opts = [None, *team_ids]
        winner = d4.selectbox("Winner", winner_opts,
                              format_func=lambda t: "—" if t is None else TEAM_NAMES[t],
                              index=_index(winner_opts, current.winner_id if current else None))
        margin = d5.number_input("Margin", min_value=0, max_value=999, step=1,
                                 value=int(current.victory_margin or 0) if current else 0)
        if st.form_submit_button("Save match", type="primary"):
            return {"match_description": desc, "match_format": fmt, "match_date": mdate,
                    "team1_id": team1, "team2_id": team2, "venue_id": venue,
                    "series_id": series, "match_status": status, "toss_winner_id": toss,
                    "toss_decision": decision, "victory_type": vtype, "winner_id": winner,
                    "victory_margin": margin or None}
    return None


def pick_match(key: str):
    c1, c2 = st.columns(2)
    fmt = c1.selectbox("Format filter", ["All", *MATCH_FORMATS], key=f"{key}_fmt")
    team = c2.selectbox("Team filter", [None, *TEAM_NAMES], key=f"{key}_team",
                        format_func=lambda t: "All teams" if t is None else TEAM_NAMES[t])
    df = matches.search(match_format=None if fmt == "All" else fmt, team_id=team, limit=150)
    if df.empty:
        st.caption("No matches match.")
        return None
    options = {f"{r.match_date} · {r.team1_name} vs {r.team2_name} · {r.match_description} "
               f"(#{r.match_id})": r.match_id for r in df.itertuples()}
    return options[st.selectbox("Match", list(options), key=f"{key}_sel")]


# ---------------------------------------------------------------- layout
player_tab, match_tab, data_tab = st.tabs(["Players", "Matches", "Import from API"])

with player_tab:
    action = st.segmented_control("Action", ["View", "Add", "Update", "Delete"],
                                  default="View", key="p_action") or "View"
    try:
        if action == "View":
            c1, c2, c3 = st.columns([2, 1, 1])
            term = c1.text_input("Search by name")
            team = c2.selectbox("Team", [None, *TEAM_NAMES],
                                format_func=lambda t: "All teams" if t is None
                                else TEAM_NAMES[t])
            role = c3.selectbox("Role", [None, *PLAYING_ROLES],
                                format_func=lambda r: "All roles" if r is None else r)
            df = players.search(name=term, team_id=team, role=role)
            st.caption(f"{len(df)} players")
            st.dataframe(df, hide_index=True, width="stretch")
            if not df.empty:
                pid = st.selectbox("Career statistics for", df["player_id"],
                                   format_func=lambda i: df.set_index("player_id")
                                   .loc[i, "full_name"])
                career = players.career(pid)
                if career.empty:
                    st.caption("No career statistics stored for this player.")
                else:
                    st.dataframe(career, hide_index=True, width="stretch")
        elif action == "Add" and require_admin():
            data = player_form("add_player")
            if data:
                new_id = players.create(data)
                saved(f"Player added (id {new_id})")
        elif action == "Update" and require_admin():
            pid, _ = pick_player("upd_player")
            if pid:
                data = player_form(f"edit_player_{pid}", players.get(pid))
                if data:
                    players.update(pid, data)
                    saved("Player updated")
        elif action == "Delete" and require_admin():
            pid, label = pick_player("del_player")
            if pid:
                st.warning(f"Delete **{label}**? Players with match history cannot be "
                           "deleted (it would corrupt scorecards).")
                if st.checkbox("I understand this cannot be undone", key="p_confirm") and \
                        st.button("Delete player", type="primary"):
                    players.delete(pid)
                    saved("Player deleted")
    except (AppError, ConfigError) as exc:
        show_error(exc)

with match_tab:
    action = st.segmented_control("Action", ["View", "Add", "Update", "Delete"],
                                  default="View", key="m_action") or "View"
    try:
        if action == "View":
            mid = pick_match("view_match")
            if mid:
                row = matches.summary_row(mid)
                st.markdown(f"**{row['team1_name']} vs {row['team2_name']}** · "
                            f"{row['match_description']} · {row['venue_name']} · "
                            f"{row['match_date']}")
                (st.success if row["match_status"] == "Completed" else st.info)(
                    row["result_text"])
                batting, bowling = matches.scorecard(mid)
                if batting.empty:
                    st.caption("No innings recorded for this match.")
                for inn in sorted(batting["innings_no"].unique()) if not batting.empty else []:
                    team = batting.loc[batting.innings_no == inn, "team_name"].iloc[0]
                    st.markdown(f"**Innings {inn} – {team}**")
                    st.dataframe(batting[batting.innings_no == inn]
                                 .drop(columns=["innings_no", "team_name"]),
                                 hide_index=True, width="stretch")
                    st.dataframe(bowling[bowling.innings_no == inn]
                                 .drop(columns=["innings_no"]),
                                 hide_index=True, width="stretch")
        elif action == "Add" and require_admin():
            data = match_form("add_match")
            if data:
                new_id = matches.create(data)
                saved(f"Match added (id {new_id})")
        elif action == "Update" and require_admin():
            mid = pick_match("upd_match")
            if mid:
                data = match_form(f"edit_match_{mid}", matches.get(mid))
                if data:
                    matches.update(mid, data)
                    saved("Match updated")
        elif action == "Delete" and require_admin():
            mid = pick_match("del_match")
            if mid:
                st.warning("Deleting a match also deletes all of its batting and bowling "
                           "innings (ON DELETE CASCADE).")
                if st.checkbox("I understand this cannot be undone", key="m_confirm") and \
                        st.button("Delete match", type="primary"):
                    matches.delete(mid)
                    saved("Match deleted")
    except (AppError, ConfigError) as exc:
        show_error(exc)

with data_tab:
    st.markdown("Load recently **completed international matches** (Test/ODI/T20I) from the "
                "Cricbuzz API into the database. Each match costs about 1–2 API calls; "
                "already-loaded matches are skipped.")
    if not settings.has_api_key:
        st.info("Add RAPIDAPI_KEY to .env to enable importing.")
    elif require_admin():
        limit = st.slider("Matches to import", 1, 10, 3)
        if st.button("Import recent matches", type="primary", icon=":material/download:"):
            from services.ingestion_service import IngestionService
            with st.spinner("Importing …"):
                try:
                    report = IngestionService().ingest_recent(limit=limit)
                    saved(f"Import {report.status}")
                    st.write(report.summary())
                    for line in report.skipped + report.failed:
                        st.caption(line)
                except (AppError, ConfigError) as exc:
                    show_error(exc)
