"""SQL Analytics page: the 25 practice questions plus a read-only SQL console."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from analytics.registry import LEVELS, QUERIES, QUERY_BY_NUMBER
from analytics.runner import run_query, run_read_only
from components.cards import page_header, show_error
from components.charts import show_chart
from config import ConfigError
from core.exceptions import AppError

page_header("SQL Database", "SQL analytics",
            "25 questions from beginner to advanced, each with its result, chart and SQL.")


@st.cache_data(ttl=300, show_spinner="Running query …")
def cached_query(number: int) -> pd.DataFrame:
    return run_query(QUERY_BY_NUMBER[number])


left, right = st.columns([1, 3])
with left:
    level = st.radio("Level", ["All", *LEVELS], horizontal=False)
    options = [q for q in QUERIES if level == "All" or q.level == level]
    spec = st.selectbox("Question", options, format_func=lambda q: q.label)
    if st.button("Re-run (ignore cache)", icon=":material/refresh:"):
        cached_query.clear()

with right:
    st.markdown(f"#### {spec.label}")
    st.markdown(f"**{spec.level}** · {spec.question()}")
    st.caption(f"SQL concepts: {spec.concepts()}")
    try:
        df = cached_query(spec.number)
    except (AppError, ConfigError) as exc:
        show_error(exc)
        st.stop()

    m = st.columns(3)
    m[0].metric("Rows", len(df))
    m[1].metric("Columns", len(df.columns))
    m[2].metric("Level", spec.level)
    if spec.insight:
        st.caption(spec.insight)

    table_tab, chart_tab, sql_tab = st.tabs(["Result", "Chart", "SQL"])
    with table_tab:
        st.dataframe(df, hide_index=True, width="stretch")
        st.download_button("Download CSV", df.to_csv(index=False).encode(),
                           file_name=f"q{spec.number:02d}.csv", mime="text/csv")
    with chart_tab:
        if not show_chart(df, spec.chart):
            st.caption("This question is best read as a table.")
    with sql_tab:
        st.code(spec.sql(), language="sql")

st.divider()
with st.expander("Custom SQL console (read-only)", icon=":material/terminal:"):
    st.caption("Run your own SELECT against the database. Writes are blocked twice: by a "
               "keyword check and by a READ ONLY transaction. Results are capped at 1,000 rows.")
    st.markdown("Useful views: `v_match_summary`, `v_batting_detail`, `v_bowling_detail`, "
                "`v_player_profile`.")
    sql = st.text_area("SQL", "SELECT team_name, COUNT(*) AS players\nFROM v_player_profile\n"
                              "GROUP BY team_name\nORDER BY players DESC", height=140)
    if st.button("Run query", type="primary"):
        try:
            st.dataframe(run_read_only(sql), hide_index=True, width="stretch")
        except ValueError as exc:
            st.warning(str(exc))
        except (AppError, ConfigError) as exc:
            show_error(exc)
