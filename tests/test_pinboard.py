"""Pinboard queries must be scoped per user, not just per guild.

Every query here used Python's `and` between two Peewee column comparisons
instead of Peewee's `&`. `a and b` evaluates to just `b`, so the pin-owner
clause was silently dropped everywhere: `/pinboard list` showed every user's
pins in the guild, the 30-pin cap was per guild rather than per user, and
`/pinboard unpin` could delete another user's pin of the same message
(allowed by the (pin_owner_id, message_id) composite key).
"""

import datetime
from types import SimpleNamespace

import pytest
from cogs.pinboard.models import PinboardPost
from cogs.pinboard.pinboard import Pinboard

from tests.test_bot import test_db  # noqa: F401  (fixture)

GUILD_ID = 1001
OTHER_GUILD_ID = 1002
USER_A = 42
USER_B = 99

pytestmark = pytest.mark.asyncio


class FakeResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, content=None, *, embed=None, ephemeral=False):
        self.messages.append(
            SimpleNamespace(content=content, embed=embed, ephemeral=ephemeral)
        )


def make_interaction(user_id, guild_id=GUILD_ID):
    return SimpleNamespace(
        user=SimpleNamespace(id=user_id),
        guild=SimpleNamespace(id=guild_id),
        response=FakeResponse(),
    )


def make_pin(message_id, pin_owner_id, guild_id=GUILD_ID, channel_id=2001):
    now = datetime.datetime.now()
    return PinboardPost.create(
        message_id=message_id,
        pin_owner_id=pin_owner_id,
        guild_id=guild_id,
        channel_id=channel_id,
        author_id=pin_owner_id,
        created_at=now,
        pinned_at=now,
    )


@pytest.fixture(autouse=True)
def tables(test_db):
    test_db.create_tables([PinboardPost])


@pytest.fixture
def cog(test_db):
    bot = SimpleNamespace(
        database=test_db, tree=SimpleNamespace(add_command=lambda *a, **k: None)
    )
    return Pinboard(bot)


async def test_get_pinned_message_ids_scoped_to_user_and_guild(cog):
    make_pin(100, pin_owner_id=USER_A, guild_id=GUILD_ID)
    make_pin(200, pin_owner_id=USER_B, guild_id=GUILD_ID)  # another user, same guild
    make_pin(
        300, pin_owner_id=USER_A, guild_id=OTHER_GUILD_ID
    )  # same user, other guild

    ids = await cog.get_pinned_message_ids(
        SimpleNamespace(id=USER_A), SimpleNamespace(id=GUILD_ID)
    )

    assert ids == [100]


async def test_unpin_only_deletes_the_callers_own_pin(cog):
    make_pin(100, pin_owner_id=USER_A, guild_id=GUILD_ID)
    make_pin(100, pin_owner_id=USER_B, guild_id=GUILD_ID)  # same message, other owner

    await Pinboard.unpin.callback(cog, make_interaction(USER_A), message_number=1)

    assert PinboardPost.select().where(PinboardPost.pin_owner_id == USER_A).count() == 0
    assert PinboardPost.select().where(PinboardPost.pin_owner_id == USER_B).count() == 1


async def test_pin_count_cap_is_scoped_to_user_and_guild(cog):
    for i in range(cog.MAX_PINNED_MESSAGES):
        make_pin(i, pin_owner_id=USER_B, guild_id=GUILD_ID)  # another user at the cap

    message = SimpleNamespace(
        id=9999,
        channel=SimpleNamespace(id=2001),
        author=SimpleNamespace(id=USER_A),
        created_at=datetime.datetime.now(),
        jump_url="https://discord.com/channels/1/2/9999",
    )
    interaction = make_interaction(USER_A)

    await cog.ctx_menu(interaction, message)

    # USER_A has no pins of their own yet, so they should not be blocked by
    # USER_B having reached the cap in the same guild.
    assert interaction.response.messages[0].content.startswith("Pinned message")
