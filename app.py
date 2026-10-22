"""Cricbuzz LiveStats - Streamlit entry point.

Run from the project root:
    streamlit run app.py

This file only configures the page and the navigation; every page lives in
``pages/``. ``st.navigation`` replaces Streamlit's automatic pages/ discovery,
which gives us readable titles, icons, grouping and a fixed order.
"""
import streamlit as st

st.set_page_config(page_title="Cricbuzz LiveStats", page_icon="🏏", layout="wide",
                   initial_sidebar_state="expanded")

from components.cards import inject_css  # noqa: E402  (set_page_config must run first)

PAGES = {
    "Overview": [
        st.Page("pages/home.py", title="Home", icon=":material/home:", default=True),
    ],
    "Cricbuzz API": [
        st.Page("pages/live_matches.py", title="Live Matches", icon=":material/sports_cricket:"),
        st.Page("pages/top_stats.py", title="Top Player Stats", icon=":material/leaderboard:"),
    ],
    "SQL Database": [
        st.Page("pages/sql_queries.py", title="SQL Analytics", icon=":material/query_stats:"),
        st.Page("pages/crud_operations.py", title="CRUD Operations", icon=":material/edit_note:"),
    ],
}

navigation = st.navigation(PAGES)
inject_css()
st.sidebar.caption("Cricbuzz LiveStats · Python · SQL · Streamlit")
navigation.run()
