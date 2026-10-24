"""The Spotify fallback embed must not survive a late native unfurl.

`on_message` and `on_raw_message_edit` hand off through `fixed_messages`, and
the handoff has to cover the window in which the reply is still being sent.

Withdrawal is conditional: once our embed has been replied to, reacted to, or
had a thread started on it, deleting it would break the conversation around it.
"""

import asyncio
import logging
import os
import sys

import pytest

os.environ.setdefault("BOT_ENV", "test")
os.environ.setdefault("DB_TYPE", "sqlite")
os.environ.setdefault("SQLITE_DB", ":memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import discord

from tests.test_bot import test_db  # noqa: F401  (fixture)

pytestmark = pytest.mark.asyncio

TRACK_URL = "https://open.spotify.com/track/6SLsBCEQaTCZ8MBgpWWPc0"
MESSAGE_ID = 555
CHANNEL_ID = 777
GUILD_ID = 42


class _Guild:
    id = GUILD_ID


class _Author:
    bot = False
    id = 1


class _Reply:
    """The bot's own fallback message."""

    def __init__(self, channel=None):
        self.id = 999
        self.deleted = False
        self.reactions = []
        self.thread = None
        self.channel = channel if channel is not None else _Channel(None)

    async def delete(self):
        self.deleted = True


class _Downstream:
    """A later message in the channel, optionally replying to something."""

    def __init__(self, replying_to=None):
        self.reference = None if replying_to is None else _Reference(replying_to)


class _Reference:
    def __init__(self, message_id):
        self.message_id = message_id


class _Channel:
    def __init__(self, fetched, downstream=()):
        self.id = CHANNEL_ID
        self._fetched = fetched
        self._downstream = list(downstream)

    async def fetch_message(self, message_id):
        return self._fetched

    def history(self, after=None, limit=None):
        async def _gen():
            for msg in self._downstream[:limit]:
                yield msg

        return _gen()


class _Message:
    def __init__(self, embeds=(), on_reply=None):
        self.id = MESSAGE_ID
        self.author = _Author()
        self.guild = _Guild()
        self.content = f"what do you think of this one {TRACK_URL}"
        self.embeds = list(embeds)
        self.channel = _Channel(self)
        self._on_reply = on_reply
        self.reply_sent = None

    async def reply(self, *a, **kw):
        self.reply_sent = _Reply(channel=self.channel)
        if self._on_reply is not None:
            await self._on_reply()
        return self.reply_sent


class _Payload:
    def __init__(self, embeds):
        self.message_id = MESSAGE_ID
        self.channel_id = CHANNEL_ID
        self.data = {"embeds": embeds}


class _Bot:
    def get_channel(self, channel_id):
        return None

    async def fetch_channel(self, channel_id):
        raise AssertionError("fetch_channel should not be reached in these tests")


def _make_cog(monkeypatch):
    """A SpotifyEmbed with the credential-dependent __init__ bypassed."""
    from cachetools import TTLCache
    from cogs.spotifyembed.spotifyembed import SpotifyEmbed

    cog = SpotifyEmbed.__new__(SpotifyEmbed)
    cog._bot = _Bot()
    cog.logger = logging.getLogger("test.spotifyembed")
    # Same shape as __init__ builds, so the expiry behaviour is the real one
    cog.fixed_messages = TTLCache(maxsize=10, ttl=SpotifyEmbed.CLEANUP_WINDOW)
    monkeypatch.setattr(
        SpotifyEmbed, "generate_track_embed", lambda self, _id: discord.Embed()
    )
    # The real listener waits on Discord's embed server; the stub message
    # already decides whether an embed showed up.
    real_sleep = asyncio.sleep
    monkeypatch.setattr(asyncio, "sleep", lambda _s: real_sleep(0))
    return cog


@pytest.fixture
def enabled_guild(test_db):  # noqa: F811
    from cogs.spotifyembed.models import SpotifyEmbedConfig

    test_db.create_tables([SpotifyEmbedConfig])
    SpotifyEmbedConfig.create(guild_id=GUILD_ID, enabled=True)


async def test_unfurl_during_send_deletes_the_reply(monkeypatch, enabled_guild):
    """The MESSAGE_UPDATE lands while reply() is still in flight."""
    cog = _make_cog(monkeypatch)
    message = _Message()

    async def unfurl_mid_send():
        await cog.on_raw_message_edit(_Payload([{"type": "link"}]))

    message._on_reply = unfurl_mid_send

    await cog.on_message(message)

    assert message.reply_sent is not None, "the fallback embed was never posted"
    assert message.reply_sent.deleted, "the fallback embed outlived the native one"
    assert MESSAGE_ID not in cog.fixed_messages


async def test_unfurl_after_send_deletes_the_reply(monkeypatch, enabled_guild):
    """The ordinary late-unfurl path: the edit arrives after reply() returns."""
    cog = _make_cog(monkeypatch)
    message = _Message()

    await cog.on_message(message)
    reply = message.reply_sent
    assert cog.fixed_messages[MESSAGE_ID] == reply.id

    monkeypatch.setattr(_Bot, "get_channel", lambda self, _id: _Channel(reply))
    await cog.on_raw_message_edit(_Payload([{"type": "link"}]))

    assert reply.deleted
    assert MESSAGE_ID not in cog.fixed_messages


async def test_no_reply_when_discord_already_unfurled(monkeypatch, enabled_guild):
    cog = _make_cog(monkeypatch)
    message = _Message(embeds=[discord.Embed()])

    await cog.on_message(message)

    assert message.reply_sent is None
    assert MESSAGE_ID not in cog.fixed_messages


async def test_edit_without_embeds_keeps_the_reply(monkeypatch, enabled_guild):
    """A plain content edit is not an unfurl and must not drop the registration."""
    cog = _make_cog(monkeypatch)
    message = _Message()

    await cog.on_message(message)
    await cog.on_raw_message_edit(_Payload([]))

    assert not message.reply_sent.deleted
    assert cog.fixed_messages[MESSAGE_ID] == message.reply_sent.id


async def test_reply_to_our_embed_keeps_it(monkeypatch, enabled_guild):
    """Deleting it would leave someone's reply pointing at nothing."""
    cog = _make_cog(monkeypatch)
    message = _Message()

    await cog.on_message(message)
    reply = message.reply_sent
    message.channel._downstream = [_Downstream(replying_to=reply.id)]

    monkeypatch.setattr(_Bot, "get_channel", lambda self, _id: message.channel)
    message.channel._fetched = reply
    await cog.on_raw_message_edit(_Payload([{"type": "link"}]))

    assert not reply.deleted


async def test_reaction_on_our_embed_keeps_it(monkeypatch, enabled_guild):
    cog = _make_cog(monkeypatch)
    message = _Message()

    await cog.on_message(message)
    reply = message.reply_sent
    reply.reactions = ["👍"]

    monkeypatch.setattr(_Bot, "get_channel", lambda self, _id: message.channel)
    message.channel._fetched = reply
    await cog.on_raw_message_edit(_Payload([{"type": "link"}]))

    assert not reply.deleted


async def test_thread_on_our_embed_keeps_it(monkeypatch, enabled_guild):
    """Deleting a thread starter takes the thread with it."""
    cog = _make_cog(monkeypatch)
    message = _Message()

    await cog.on_message(message)
    reply = message.reply_sent
    reply.thread = object()

    monkeypatch.setattr(_Bot, "get_channel", lambda self, _id: message.channel)
    message.channel._fetched = reply
    await cog.on_raw_message_edit(_Payload([{"type": "link"}]))

    assert not reply.deleted


async def test_unrelated_downstream_messages_do_not_block_removal(
    monkeypatch, enabled_guild
):
    """Ordinary chatter after our embed is not engagement with it."""
    cog = _make_cog(monkeypatch)
    message = _Message()

    await cog.on_message(message)
    reply = message.reply_sent
    message.channel._downstream = [
        _Downstream(),
        _Downstream(replying_to=12345),  # a reply, but to something else
    ]

    monkeypatch.setattr(_Bot, "get_channel", lambda self, _id: message.channel)
    message.channel._fetched = reply
    await cog.on_raw_message_edit(_Payload([{"type": "link"}]))

    assert reply.deleted


async def test_registration_expires_after_the_cleanup_window(
    monkeypatch, enabled_guild
):
    """A unfurl arriving days later finds nothing registered."""
    from cogs.spotifyembed.spotifyembed import SpotifyEmbed

    cog = _make_cog(monkeypatch)
    assert cog.fixed_messages.ttl == SpotifyEmbed.CLEANUP_WINDOW

    message = _Message()
    await cog.on_message(message)
    assert MESSAGE_ID in cog.fixed_messages

    cog.fixed_messages.expire(
        cog.fixed_messages.timer() + SpotifyEmbed.CLEANUP_WINDOW + 1
    )
    assert MESSAGE_ID not in cog.fixed_messages
