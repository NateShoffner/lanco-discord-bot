"""Forecast rendering tests.

The rendering helpers are pure so they can be checked without touching the
OpenWeatherMap API. The two things worth pinning are that entries are shown in
the forecast location's timezone rather than the bot's, and that a dry entry
prints no precipitation chance at all.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest
import pytz
from cogs.weather.weather import (
    DAILY_DAYS,
    FALLBACK_COLOR,
    FALLBACK_EMOJI,
    HOURLY_HOURS,
    _color_for,
    _emoji_for,
    _format_hour,
    _pop_suffix,
    build_forecast_embed,
    render_daily_row,
    render_hourly_row,
)

UTC = pytz.UTC


def test_unknown_icon_degrades_instead_of_raising():
    # The command used to index the colour map directly, so an icon outside
    # the documented set would have raised KeyError mid-render.
    assert _color_for("99z") == FALLBACK_COLOR
    assert _emoji_for("99z") == FALLBACK_EMOJI
    assert _color_for(None) == FALLBACK_COLOR
    assert _emoji_for("") == FALLBACK_EMOJI


def test_icon_lookup_ignores_day_night_suffix():
    assert _color_for("04d") == _color_for("04n")
    assert _emoji_for("01d") == _emoji_for("01n")


@pytest.mark.parametrize(
    "pop,expected",
    [(0, ""), (None, ""), (0.5, "50%"), (1, "100%"), (0.666, "67%")],
)
def test_pop_suffix(pop, expected):
    suffix = _pop_suffix(pop)
    if expected:
        assert expected in suffix
    else:
        assert suffix == ""


@pytest.mark.parametrize(
    "hour,expected",
    [(0, "12 AM"), (4, "4 AM"), (12, "12 PM"), (13, "1 PM"), (23, "11 PM")],
)
def test_format_hour_has_no_leading_zero(hour, expected):
    # Built by hand because strftime's %-I is glibc-only and raises on Windows.
    assert _format_hour(datetime(2026, 8, 22, hour)) == expected


def test_render_daily_row():
    row = render_daily_row(datetime(2026, 8, 22), "10d", 74, 63, "Rain", 1)
    assert "Sat 08/22" in row
    assert "74" in row and "63" in row
    assert "Rain" in row
    assert "100%" in row


def test_render_hourly_row_omits_dry_precipitation():
    wet = render_hourly_row(datetime(2026, 8, 22, 13), "10d", 73, "Rain", 0.91)
    dry = render_hourly_row(datetime(2026, 8, 22, 13), "01d", 73, "Clear", 0)
    assert "91%" in wet
    assert "%" not in dry
    assert "1 PM" in dry


def _weather(ts, icon, status, pop, temps):
    return SimpleNamespace(
        reference_time=lambda *a, **k: ts,
        weather_icon_name=icon,
        status=status,
        precipitation_probability=pop,
        temperature=lambda unit: temps,
    )


def _one_call(timezone="America/New_York", hourly_n=48, daily_n=8):
    # 2026-08-22 12:00 UTC is 08:00 in New York, which is what the rendered
    # rows should say.
    base = int(datetime(2026, 8, 22, 12, tzinfo=UTC).timestamp())
    return SimpleNamespace(
        timezone=timezone,
        forecast_hourly=[
            _weather(base + i * 3600, "01d", "Clear", 0, {"temp": 70 + i})
            for i in range(hourly_n)
        ],
        forecast_daily=[
            _weather(base + i * 86400, "10d", "Rain", 1, {"max": 80 + i, "min": 60 + i})
            for i in range(daily_n)
        ],
    )


def test_entries_render_in_the_forecast_locations_timezone():
    # The same instant is a different wall clock in each zone. Rendering in the
    # bot's own timezone would label a forecast for elsewhere with wrong hours.
    eastern = build_forecast_embed("x", _one_call("America/New_York"), hourly=True)
    pacific = build_forecast_embed("x", _one_call("America/Los_Angeles"), hourly=True)

    assert "8 AM" in eastern.description.split("\n")[0]
    assert "5 AM" in pacific.description.split("\n")[0]
    assert "America/New_York" in eastern.footer.text


def test_views_are_trimmed_to_their_limits():
    hourly = build_forecast_embed("x", _one_call(), hourly=True)
    daily = build_forecast_embed("x", _one_call(), hourly=False)

    assert len(hourly.description.split("\n")) == HOURLY_HOURS
    assert len(daily.description.split("\n")) == DAILY_DAYS
    assert daily.title.startswith(f"{DAILY_DAYS}-day")
    assert "Hourly" in hourly.title


def test_short_forecast_titles_itself_by_actual_length():
    # OWM can return fewer entries than we ask for; the title must not claim
    # more days than the embed actually lists.
    embed = build_forecast_embed("x", _one_call(daily_n=3), hourly=False)
    assert embed.title.startswith("3-day")
    assert len(embed.description.split("\n")) == 3


def test_embed_stays_within_discord_description_limit():
    for hourly in (True, False):
        embed = build_forecast_embed("x", _one_call(), hourly=hourly)
        assert len(embed.description) < 4096
