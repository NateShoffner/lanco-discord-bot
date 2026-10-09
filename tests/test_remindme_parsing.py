"""`!remindme` must accept a duration that names a timezone.

dateparser returns an aware datetime whenever the input mentions a zone
("3pm UTC", "tomorrow 9am EST") and a naive one otherwise. Subtracting the
naive `datetime.now()` from an aware result raises TypeError, so the command
blew up instead of setting the reminder. The column and `issue_reminders` both
work in naive local time, so an aware parse is converted to match.
"""

import datetime

import dateparser
import pytest

UTC = datetime.timezone.utc


def _normalize(remind_time: datetime.datetime) -> datetime.datetime:
    """The conversion as remindme.py does it."""
    if remind_time.tzinfo is not None:
        remind_time = remind_time.astimezone().replace(tzinfo=None)
    return remind_time


@pytest.mark.parametrize("duration", ["2h", "30m", "tomorrow"])
def test_a_bare_duration_is_already_naive(duration):
    parsed = dateparser.parse(duration, settings={"PREFER_DATES_FROM": "future"})
    assert parsed is not None
    normalized = _normalize(parsed)
    assert normalized.tzinfo is None
    # the subtraction the command does next
    assert isinstance(normalized - datetime.datetime.now(), datetime.timedelta)


def test_an_aware_parse_becomes_comparable_to_a_naive_now():
    aware = datetime.datetime.now(UTC) + datetime.timedelta(hours=2)
    assert aware.tzinfo is not None
    with pytest.raises(TypeError):
        aware - datetime.datetime.now()

    normalized = _normalize(aware)
    assert normalized.tzinfo is None
    delta = normalized - datetime.datetime.now()
    assert 0 < delta.total_seconds() <= 2 * 3600


def test_normalizing_preserves_the_instant_in_local_terms():
    """Dropping the tzinfo without converting would shift the reminder by the
    offset, firing it hours early or late.
    """
    aware = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    expected = aware.astimezone().replace(tzinfo=None)
    assert _normalize(aware) == expected


def test_the_cog_applies_the_conversion():
    """Keeps the helper above honest about what the command actually does."""
    import inspect

    from cogs.remindme.remindme import RemindMe

    # the attribute is a Command, the body lives on its callback
    source = inspect.getsource(RemindMe.remindme.callback)
    assert "tzinfo is not None" in source
    assert "astimezone().replace(tzinfo=None)" in source
