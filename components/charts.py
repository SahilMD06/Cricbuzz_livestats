"""Plotly chart helpers driven by ``ChartSpec`` metadata.

One place decides colours, fonts and layout so every chart in the app looks
like part of the same system and stays readable on the dark theme.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analytics.registry import ChartSpec

PALETTE = ["#14B8A6", "#E8A33D", "#E879F9", "#60A5FA", "#F0616D", "#A3E635",
           "#F59E0B", "#94A3B8"]
MAX_CATEGORIES = 15

# Traces get their colours when created, so the palette must be the px default.
px.defaults.color_discrete_sequence = PALETTE


def _style(fig: go.Figure, title: str = "") -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=15)), template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", color="#E5E7EB", size=12),
        margin=dict(l=10, r=10, t=50, b=10), legend=dict(title=None),
        colorway=PALETTE, height=420)
    fig.update_xaxes(gridcolor="#1F2C42", zeroline=False)
    fig.update_yaxes(gridcolor="#1F2C42", zeroline=False)
    return fig


def _numeric(df: pd.DataFrame, cols) -> pd.DataFrame:
    df = df.copy()
    for c in ([cols] if isinstance(cols, str) else cols):
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def build_chart(df: pd.DataFrame, spec: ChartSpec) -> go.Figure | None:
    """Return a Plotly figure for ``df`` according to ``spec`` (None if not drawable)."""
    if df.empty or spec.x not in df:
        return None
    ys = spec.y if isinstance(spec.y, tuple) else (spec.y,)
    if spec.kind != "pie" and any(y not in df for y in ys):
        return None
    color = spec.color if spec.color and spec.color in df else None

    if spec.kind == "pie":
        if spec.y in df and pd.api.types.is_numeric_dtype(_numeric(df, spec.y)[spec.y]) \
                and spec.y != "full_name":
            data = _numeric(df, spec.y)
            fig = px.pie(data, names=spec.x, values=spec.y, hole=0.55)
        else:                                       # count rows per category
            counts = df[spec.x].value_counts().reset_index()
            counts.columns = [spec.x, "count"]
            fig = px.pie(counts, names=spec.x, values="count", hole=0.55)
        fig.update_traces(textinfo="label+percent",
                          marker=dict(line=dict(color="#0B1220", width=2)))
        return _style(fig, spec.title)

    data = _numeric(df, ys)
    if spec.kind in ("bar", "barh", "grouped_bar"):
        data = data.head(MAX_CATEGORIES)
    if spec.kind == "bar":
        fig = px.bar(data, x=spec.x, y=ys[0], color=color, text_auto=True)
    elif spec.kind == "barh":
        data = data.iloc[::-1]                       # largest at the top
        fig = px.bar(data, x=ys[0], y=spec.x, color=color, orientation="h", text_auto=True)
    elif spec.kind == "grouped_bar":
        long = data.melt(id_vars=[spec.x], value_vars=list(ys), var_name="measure",
                         value_name="value")
        fig = px.bar(long, x=spec.x, y="value", color="measure", barmode="group")
    elif spec.kind == "line":
        top = data[color].value_counts().head(8).index if color else None
        if color is not None:
            data = data[data[color].isin(top)]
        fig = px.line(data.sort_values(spec.x), x=spec.x, y=ys[0], color=color, markers=True)
    elif spec.kind == "scatter":
        hover = "full_name" if "full_name" in data else None
        fig = px.scatter(data, x=spec.x, y=ys[0], color=color, hover_name=hover)
        fig.update_traces(marker=dict(size=9, opacity=0.85))
        if color and data[color].nunique() > 8:
            fig.update_layout(showlegend=False)
    else:
        return None
    fig.update_traces(selector=dict(type="bar"), marker_line_width=0)
    return _style(fig, spec.title)


def show_chart(df: pd.DataFrame, spec: ChartSpec | None) -> bool:
    """Render the chart if one is defined and drawable; return True if shown."""
    if spec is None:
        return False
    fig = build_chart(df, spec)
    if fig is None:
        return False
    st.plotly_chart(fig, width="stretch")
    return True


def simple_bar(df: pd.DataFrame, x: str, y: str, title: str = "",
               horizontal: bool = True) -> None:
    """Quick bar chart used by the Live and Top Stats pages."""
    spec = ChartSpec("barh" if horizontal else "bar", x, y, title=title)
    fig = build_chart(df, spec)
    if fig is not None:
        st.plotly_chart(fig, width="stretch")
