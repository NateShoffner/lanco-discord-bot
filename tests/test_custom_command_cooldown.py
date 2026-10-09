"""A custom command's cooldown has to actually stop it running.

The modal collects a cooldown, `CustomCommands.cooldown` stores it, and the
command list renders it, so a guild admin had every reason to think it worked.
The dispatcher had a `# TODO handle cooldowns` where the check belonged, so the
setting did nothing at all.
"""

import datetime

import pytest
from cogs.commands.commands import Commands
from cogs.commands.models import CustomCommands
from db import database_proxy
from peewee import SqliteDatabase

UTC = datetime.timezone.utc


@pytest.fixture(autouse=True)
def test_db():
    db = SqliteDatabase(":memory:")
    database_proxy.initialize(db)
    db.connect()
    db.create_tables([CustomCommands])
    yield db
    db.close()


def _command(cooldown=0, last_used=None):
    return CustomCommands.create(
        guild_id=1,
        command_name="glizzy",
        command_response="hi",
        cooldown=cooldown,
        last_used=last_used,
    )


def test_no_cooldown_configured_is_always_ready():
    assert Commands.remaining_cooldown(_command(cooldown=0)) == 0


def test_never_used_is_ready():
    assert Commands.remaining_cooldown(_command(cooldown=60)) == 0


def test_a_recent_use_still_has_time_left():
    recent = datetime.datetime.now(UTC) - datetime.timedelta(seconds=10)
    remaining = Commands.remaining_cooldown(_command(cooldown=60, last_used=recent))
    assert 45 < remaining <= 50


def test_an_expired_cooldown_is_ready_again():
    old = datetime.datetime.now(UTC) - datetime.timedelta(seconds=120)
    assert Commands.remaining_cooldown(_command(cooldown=60, last_used=old)) == 0


def test_a_naive_stored_timestamp_is_read_as_utc():
    """A row written before this is naive; reading it as local time would make
    the cooldown look expired, or hours long, depending on the offset.
    """
    naive = datetime.datetime.now(UTC).replace(tzinfo=None) - datetime.timedelta(
        seconds=10
    )
    remaining = Commands.remaining_cooldown(_command(cooldown=60, last_used=naive))
    assert 45 < remaining <= 50


def test_an_offset_bearing_string_is_parsed():
    """discord.utils.utcnow() round-trips through SQLite as a string peewee
    cannot parse, so it comes back as a str rather than a datetime.
    """
    recent = datetime.datetime.now(UTC) - datetime.timedelta(seconds=10)
    command = _command(cooldown=60)
    command.last_used = str(recent)
    remaining = Commands.remaining_cooldown(command)
    assert 45 < remaining <= 50


def test_an_unparseable_timestamp_does_not_block_the_command():
    command = _command(cooldown=60)
    command.last_used = "not a timestamp"
    assert Commands.remaining_cooldown(command) == 0
