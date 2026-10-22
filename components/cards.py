"""Shared UI pieces: page styling, headers, match cards and error display.

Any text that came from the API or the database is passed through
``html.escape`` before being placed inside custom HTML, so a team or player
name can never inject markup into the page.
"""
from __future__ import annotations

import html

import streamlit as st

from config import ConfigError
from core.exceptions import (APIAuthError, APIRateLimitError, AppError,
                             DatabaseConnectionError, ValidationError)
from models.entities import MatchCard

ACCENT = "#14B8A6"
GOLD = "#E8A33D"

_CSS = f"""
<style>
/* Theme-neutral: translucent surfaces + inherited text colour, so the same
   styling reads well in both the dark (default) and light Streamlit themes. */
.block-container {{ padding-top: 3.2rem; max-width: 1300px; }}
h1, h2, h3 {{ letter-spacing: -0.01em; }}
.cb-eyebrow {{ color: {ACCENT}; font-size: 0.75rem; font-weight: 700;
              letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 0.2rem; }}
.cb-sub {{ opacity: 0.7; margin-top: -0.6rem; margin-bottom: 1.2rem; }}
.cb-card {{ background: rgba(128, 140, 160, 0.08); border: 1px solid rgba(128, 140, 160, 0.25);
           border-radius: 12px; padding: 14px 16px; margin-bottom: 12px; }}
.cb-card .meta {{ opacity: 0.7; font-size: 0.78rem; }}
.cb-card .row {{ display: flex; justify-content: space-between; align-items: baseline;
                gap: 12px; font-weight: 600; margin-top: 6px; }}
.cb-card .score {{ font-variant-numeric: tabular-nums; }}
.cb-card .status {{ color: {GOLD}; font-size: 0.85rem; margin-top: 8px; }}
.cb-pill {{ display: inline-block; border: 1px solid rgba(128, 140, 160, 0.45);
           border-radius: 999px; padding: 1px 9px; font-size: 0.72rem; margin-right: 6px; }}
.cb-pill.live {{ border-color: #F0616D; color: #F0616D; }}
div[data-testid="stMetric"] {{ background: rgba(128, 140, 160, 0.08);
                               border: 1px solid rgba(128, 140, 160, 0.25);
                               border-radius: 12px; padding: 10px 14px; }}
</style>
"""


def inject_css() -> None:
    """Apply the shared page styling (call once per run, from app.py)."""
    st.markdown(_CSS, unsafe_allow_html=True)


def page_header(eyebrow: str, title: str, subtitle: str = "") -> None:
    """Consistent page heading."""
    st.markdown(f'<div class="cb-eyebrow">{html.escape(eyebrow)}</div>', unsafe_allow_html=True)
    st.title(title)
    if subtitle:
        st.markdown(f'<div class="cb-sub">{html.escape(subtitle)}</div>', unsafe_allow_html=True)


def match_card(card: MatchCard) -> None:
    """Render one live/recent/upcoming match as a card."""
    e = html.escape
    live = card.state.lower() in ("in progress", "live", "innings break", "stumps", "tea",
                                  "lunch", "drinks")
    pill = '<span class="cb-pill live">LIVE</span>' if live else ""
    when = card.start_date.strftime("%d %b %Y") if card.start_date else ""
    st.markdown(f"""
<div class="cb-card">
  <div class="meta">{pill}<span class="cb-pill">{e(card.match_format)}</span>
     {e(card.description)} · {e(card.series_name)}</div>
  <div class="row"><span>{e(card.team1 or card.team1_short)}</span>
     <span class="score">{e(card.team1_score)}</span></div>
  <div class="row"><span>{e(card.team2 or card.team2_short)}</span>
     <span class="score">{e(card.team2_score)}</span></div>
  <div class="status">{e(card.status or card.state)}</div>
  <div class="meta">{e(card.venue)}{' · ' + e(when) if when else ''}</div>
</div>""", unsafe_allow_html=True)


def show_error(exc: Exception) -> None:
    """Friendly, specific error messages; technical detail in an expander."""
    if isinstance(exc, ConfigError):
        st.warning(f"Configuration needed: {exc}")
        return
    if isinstance(exc, ValidationError):
        st.error("Please fix the following:\n\n" + "\n".join(f"- {m}" for m in exc.errors))
        return
    if isinstance(exc, APIAuthError):
        st.warning(f"Cricbuzz API unavailable: {exc.message}")
    elif isinstance(exc, APIRateLimitError):
        st.warning(f"Cricbuzz API limit reached: {exc.message}")
    elif isinstance(exc, DatabaseConnectionError):
        st.error(f"Database unreachable: {exc.message}")
    elif isinstance(exc, AppError):
        st.error(exc.message)
    else:
        st.error(f"Unexpected error: {exc}")
    detail = getattr(exc, "detail", None)
    if detail:
        with st.expander("Technical details"):
            st.code(str(detail)[:2000])


def api_key_missing_notice() -> None:
    """Explain how to enable the API-powered pages."""
    st.info("**Cricbuzz API key not configured.** Add `RAPIDAPI_KEY=...` to `.env` "
            "(or Streamlit secrets) after subscribing to the free *Cricbuzz Cricket* plan "
            "on RapidAPI. Showing data from the database instead.")
