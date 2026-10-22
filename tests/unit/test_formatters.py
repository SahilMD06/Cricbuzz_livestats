"""Cricket arithmetic helpers."""
from datetime import date

import pytest

from utils.formatters import (balls_to_overs, batting_average, economy_rate, epoch_ms_to_date,
                              format_score, overs_to_balls, strike_rate, to_int)


@pytest.mark.parametrize("overs, balls", [(8.3, 51), ("10", 60), ("0.5", 5), (None, 0),
                                          ("", 0), (4, 24)])
def test_overs_to_balls(overs, balls):
    assert overs_to_balls(overs) == balls


def test_overs_are_not_decimals():
    # 8.3 overs is 51 balls, not 8.3 * 6 = 49.8
    assert overs_to_balls(8.3) != round(8.3 * 6)


@pytest.mark.parametrize("balls, text", [(51, "8.3"), (48, "8"), (0, "0"), (None, "0")])
def test_balls_to_overs(balls, text):
    assert balls_to_overs(balls) == text


def test_rates_handle_zero_denominators():
    assert strike_rate(10, 0) is None
    assert economy_rate(10, 0) is None
    assert batting_average(100, 0) is None
    assert strike_rate(50, 40) == 125.0
    assert economy_rate(30, 36) == 5.0


def test_format_score():
    assert format_score(210, 3, 38.4) == "210/3 (38.4 ov)"
    assert format_score(250, 10) == "250"
    assert format_score(None) == "-"


def test_epoch_ms_to_date():
    assert epoch_ms_to_date("1760941800000") == date(2025, 10, 20)
    assert epoch_ms_to_date("not a number") is None


@pytest.mark.parametrize("raw, value", [("1,32,000", 132000), ("45*", 45), ("-", None),
                                        (None, None), ("12.0", 12), (7, 7)])
def test_to_int(raw, value):
    assert to_int(raw) == value
