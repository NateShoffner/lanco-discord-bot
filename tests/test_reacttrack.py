"""ReactTrack tests.

Reaction timestamps are stored timezone-aware, and peewee 4 hands them back as
aware datetimes where peewee 3 handed back the raw string. The "today" command
does arithmetic on them, so it is driven here against rows written the same
way the listeners write them.
"""

import datetime
from types import SimpleNamespace

import discord
import pytest
from cogs.reacttrack.models import ReactEvent
from cogs.reacttrack.reacttrack import ReactTrack

from tests.test_bot import test_db  # noqa: F401  (fixture)

GUILD_ID = 1001
USER_ID = 42


class FakeResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, content=None, *, embed=None, ephemeral=False):
        self.messages.append(
            SimpleNamespace(content=content, embed=embed, ephemeral=ephemeral)
        )


def make_interaction(guild_id=GUILD_ID):
    return SimpleNamespace(guild=SimpleNamespace(id=guild_id), response=FakeResponse())


def make_user(user_id=USER_ID):
    return SimpleNamespace(id=user_id, mention=f"<@{user_id}>")


def react(emoji, *, hours_ago, user_id=USER_ID, guild_id=GUILD_ID, added=True):
    return ReactEvent.create(
        message_id=1,
        channel_id=2,
        guild_id=guild_id,
        user_id=user_id,
        emoji=emoji,
        timestamp=discord.utils.utcnow() - datetime.timedelta(hours=hours_ago),
        added=added,
    )


@pytest.fixture(autouse=True)
def tables(test_db):
    test_db.create_tables([ReactEvent])


@pytest.fixture
def cog(test_db):
    return ReactTrack(SimpleNamespace(database=test_db))


def test_timestamp_round_trips_as_aware_datetime():
    react("👍", hours_ago=1)
    stored = ReactEvent.get().timestamp
    assert isinstance(stored, datetime.datetime)
    assert stored.tzinfo is not None


@pytest.mark.asyncio
async def test_today_reports_counts_and_rate(cog):
    react("👍", hours_ago=1)
    react("👍", hours_ago=2)
    react("🎉", hours_ago=4)

    interaction = make_interaction()
    await ReactTrack.view.callback(cog, interaction, make_user())

    description = interaction.response.messages[0].embed.description
    assert "1: 👍 - Used 2 times" in description
    assert "2: 🎉 - Used 1 times" in description
    assert "Total reactions: 3" in description
    # Three reactions since the oldest one, four hours ago.
    assert "Reactions per hour: 0.75" in description


@pytest.mark.asyncio
async def test_today_window_is_24_hours_in_utc(cog):
    # Either side of the cutoff by less than any UTC offset, so a naive
    # local-time cutoff would get at least one of these wrong.
    react("👍", hours_ago=23.5)
    react("🎉", hours_ago=24.5)

    interaction = make_interaction()
    await ReactTrack.view.callback(cog, interaction, make_user())

    description = interaction.response.messages[0].embed.description
    assert "👍" in description
    assert "🎉" not in description
    assert "Total reactions: 1" in description


@pytest.mark.asyncio
async def test_today_ignores_other_users_guilds_and_removals(cog):
    react("👍", hours_ago=1, user_id=USER_ID + 1)
    react("👍", hours_ago=1, guild_id=GUILD_ID + 1)
    react("👍", hours_ago=1, added=False)

    interaction = make_interaction()
    await ReactTrack.view.callback(cog, interaction, make_user())

    message = interaction.response.messages[0]
    assert message.content == "No reactions found"
    assert message.embed is None
