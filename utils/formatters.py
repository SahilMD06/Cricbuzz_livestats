"""Small, pure helpers for cricket arithmetic and display formatting.

Every function here is pure (no I/O), so it is trivial to unit test.
"""
from __future__ import annotations

from datetime import date, datetime, timezone


def overs_to_balls(overs: float | str | None) -> int:
    """Convert cricket overs notation to balls: 8.3 -> 51 (8 overs + 3 balls).

    Cricket overs are NOT decimals: 8.3 means 8 overs and 3 balls, so
    ``8.3 * 6`` (49.8) would be wrong.
    """
    if overs in (None, ""):
        return 0
    text = str(overs).strip()
    whole, _, part = text.partition(".")
    balls = int(whole or 0) * 6 + int(part[:1] or 0)
    return max(balls, 0)


def balls_to_overs(balls: int | None) -> str:
    """Convert balls to overs notation: 51 -> '8.3', 48 -> '8'."""
    if not balls:
        return "0"
    full, rem = divmod(int(balls), 6)
    return f"{full}.{rem}" if rem else str(full)


def strike_rate(runs: int, balls: int) -> float | None:
    """Batting strike rate (runs per 100 balls); None if no balls faced."""
    return round(runs * 100 / balls, 2) if balls else None


def economy_rate(runs_conceded: int, balls: int) -> float | None:
    """Bowling economy (runs per over); None if no balls bowled."""
    return round(runs_conceded * 6 / balls, 2) if balls else None


def batting_average(runs: int, dismissals: int) -> float | None:
    """Runs per dismissal; None when never dismissed (avoids divide-by-zero)."""
    return round(runs / dismissals, 2) if dismissals else None


def format_score(runs: int | None, wickets: int | None = None,
                 overs: float | str | None = None) -> str:
    """Display a team score: (210, 3, 38.4) -> '210/3 (38.4 ov)'."""
    if runs is None:
        return "-"
    score = f"{runs}" if wickets in (None, 10) else f"{runs}/{wickets}"
    return f"{score} ({overs} ov)" if overs not in (None, "") else score


def epoch_ms_to_date(value: int | str | None) -> date | None:
    """Convert Cricbuzz epoch-milliseconds (often a string) to a UTC date."""
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).date()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def to_int(value, default: int | None = None) -> int | None:
    """Parse ints from API strings like '1,32,000', '45*', '-' or None."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).replace(",", "").replace("*", "").strip()
    if text in ("", "-", "--", "null"):
        return default
    try:
        return int(float(text))
    except ValueError:
        return default


def to_float(value, default: float | None = None) -> float | None:
    """Parse floats from API strings; '-' / '' / None -> default."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").strip()
    if text in ("", "-", "--", "null"):
        return default
    try:
        return float(text)
    except ValueError:
        return default
