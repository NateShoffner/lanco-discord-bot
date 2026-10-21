"""TrendingChannel must stay inside Discord's edit bucket and fall back cleanly.

Discord allows two channel name or topic edits per ten minutes, and discord.py
sleeps on an exhausted bucket instead of raising. The original cog edited on a
fixed 30 second loop with no persistence, so it stalled after two renames,
forgot every enabled channel on restart, and one deleted channel aborted the
iteration for all the others. These tests pin the replacements: a persisted
cooldown and new-message threshold gate the model call, an edit that cannot
happen becomes a summary message, and a bad channel is skipped, not fatal.
"""

import asyncio
import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest
from cogs.trendingchannel.models import TrendingChannelConfig
from cogs.trendingchannel.trendingchannel import (
    MIN_NEW_MESSAGES,
    UPDATE_COOLDOWN,
    ChannelPulse,
    TrendingChannel,
    sanitize_channel_name,
)

from tests.test_bot import test_db  # noqa: F401  (fixture)

pytestmark = pytest.mark.asyncio

GUILD_ID = 1001
CHANNEL_ID = 2001


@pytest.fixture(autouse=True)
def tables(test_db):
    test_db.create_tables([TrendingChannelConfig])


@pytest.fixture
def cog(test_db):
    bot = SimpleNamespace(
        database=test_db,
        tree=SimpleNamespace(add_command=lambda *a, **k: None),
        get_channel=lambda cid: None,
    )
    return TrendingChannel(bot)


def make_pulse(
    name="python-packaging", topic="Talking about wheels", summary="Wheels!"
):
    return ChannelPulse(
        topics=["packaging"],
        channel_name=name,
        channel_topic=topic,
        announcement=summary,
    )


def make_messages(count, start_id=100):
    author = SimpleNamespace(display_name="nate", bot=False)
    return [
        SimpleNamespace(id=start_id + i, author=author, content=f"message {i}")
        for i in range(count - 1, -1, -1)  # newest first, like channel.history
    ]


def make_channel(
    *,
    name="general",
    topic=None,
    last_message_id=500,
    manage_channels=True,
    send_messages=True,
):
    perms = SimpleNamespace(
        manage_channels=manage_channels, send_messages=send_messages
    )
    sent = SimpleNamespace(id=last_message_id + 1000)
    channel = SimpleNamespace(
        id=CHANNEL_ID,
        name=name,
        mention=f"#{name}",
        topic=topic,
        last_message_id=last_message_id,
        guild=SimpleNamespace(id=GUILD_ID, me=object()),
        permissions_for=lambda member: perms,
        edit=AsyncMock(),
        send=AsyncMock(return_value=sent),
    )
    return channel


def make_config(**overrides):
    fields = dict(guild_id=GUILD_ID, channel_id=CHANNEL_ID)
    fields.update(overrides)
    return TrendingChannelConfig.create(**fields)


def wire(cog, monkeypatch, messages, pulse):
    """Replace the Discord fetch and the model call with canned results."""
    fetch = AsyncMock(return_value=messages)
    analyze = AsyncMock(return_value=pulse)
    monkeypatch.setattr("cogs.trendingchannel.trendingchannel.get_user_messages", fetch)
    monkeypatch.setattr(cog, "analyze", analyze)
    return fetch, analyze


# ---------------------------------------------------------------------------
# name sanitizing


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Python Packaging", "python-packaging"),
        ("  wheels & eggs!! ", "wheels-eggs"),
        ("snake_case_name", "snake-case-name"),
        ("--double--hyphens--", "double-hyphens"),
        ("x" * 150, "x" * 100),
        ("!!!", ""),
    ],
)
async def test_sanitize_channel_name(raw, expected):
    assert sanitize_channel_name(raw) == expected


# ---------------------------------------------------------------------------
# gating: when the model is and is not asked


async def test_idle_channel_costs_nothing(cog, monkeypatch):
    config = make_config(last_seen_message_id=500)
    channel = make_channel(last_message_id=500)
    fetch, analyze = wire(cog, monkeypatch, make_messages(10), make_pulse())

    assert await cog.process_channel(config, channel) is None
    fetch.assert_not_awaited()
    analyze.assert_not_awaited()


async def test_too_few_new_messages_skips_model(cog, monkeypatch):
    config = make_config(last_analyzed_message_id=105)
    channel = make_channel(last_message_id=109)
    # ids 100..109, only 106..109 are new: one short of the threshold
    messages = make_messages(10)
    assert MIN_NEW_MESSAGES == 5
    fetch, analyze = wire(cog, monkeypatch, messages, make_pulse())

    assert await cog.process_channel(config, channel) is None
    fetch.assert_awaited_once()
    analyze.assert_not_awaited()
    # the cheap gate now knows about these messages, so the next poll is free
    assert TrendingChannelConfig.get().last_seen_message_id == 109


async def test_cooldown_blocks_even_with_new_messages(cog, monkeypatch):
    recent = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    config = make_config(last_updated_at=recent - UPDATE_COOLDOWN / 2)
    channel = make_channel()
    fetch, analyze = wire(cog, monkeypatch, make_messages(10), make_pulse())

    assert await cog.process_channel(config, channel) is None
    fetch.assert_not_awaited()
    analyze.assert_not_awaited()


async def test_cooldown_elapsed_runs(cog, monkeypatch):
    recent = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    config = make_config(last_updated_at=recent - UPDATE_COOLDOWN * 2)
    channel = make_channel()
    wire(cog, monkeypatch, make_messages(10), make_pulse())

    assert await cog.process_channel(config, channel) == "edited"


async def test_force_ignores_threshold_but_not_cooldown(cog, monkeypatch):
    config = make_config(last_analyzed_message_id=108)
    channel = make_channel(last_message_id=109)
    wire(cog, monkeypatch, make_messages(10), make_pulse())

    assert await cog.process_channel(config, channel, force=True) == "edited"

    # now inside the cooldown
    config = TrendingChannelConfig.get()
    assert await cog.process_channel(config, channel, force=True) is None


# ---------------------------------------------------------------------------
# applying the result


async def test_edit_sets_name_and_topic_and_records_state(cog, monkeypatch):
    config = make_config()
    channel = make_channel()
    wire(cog, monkeypatch, make_messages(10), make_pulse())

    assert await cog.process_channel(config, channel) == "edited"
    channel.edit.assert_awaited_once()
    kwargs = channel.edit.await_args.kwargs
    assert kwargs["name"] == "python-packaging"
    assert kwargs["topic"] == "Talking about wheels"
    channel.send.assert_not_awaited()

    saved = TrendingChannelConfig.get()
    assert saved.last_name == "python-packaging"
    assert saved.last_topic == "Talking about wheels"
    assert saved.last_analyzed_message_id == 109
    assert saved.last_updated_at is not None


async def test_unchanged_name_and_topic_are_not_resent(cog, monkeypatch):
    config = make_config()
    channel = make_channel(name="python-packaging", topic="Talking about wheels")
    wire(cog, monkeypatch, make_messages(10), make_pulse())

    assert await cog.process_channel(config, channel) == "unchanged"
    channel.edit.assert_not_awaited()
    channel.send.assert_not_awaited()


async def test_only_changed_fields_are_sent(cog, monkeypatch):
    config = make_config()
    channel = make_channel(name="python-packaging", topic="old topic")
    wire(cog, monkeypatch, make_messages(10), make_pulse())

    await cog.process_channel(config, channel)
    assert channel.edit.await_args.kwargs.keys() == {"topic", "reason"}


async def test_unusable_name_keeps_current_name(cog, monkeypatch):
    config = make_config()
    channel = make_channel(name="general", topic="old topic")
    wire(cog, monkeypatch, make_messages(10), make_pulse(name="!!!"))

    await cog.process_channel(config, channel)
    assert "name" not in channel.edit.await_args.kwargs


async def test_no_manage_channels_announces_instead(cog, monkeypatch):
    config = make_config()
    channel = make_channel(manage_channels=False)
    wire(cog, monkeypatch, make_messages(10), make_pulse(summary="Wheels!"))

    assert await cog.process_channel(config, channel) == "announced"
    channel.edit.assert_not_awaited()
    channel.send.assert_awaited_once_with("Wheels!")
    # the announcement must not count as new activity on the next poll
    assert (
        TrendingChannelConfig.get().last_seen_message_id == channel.send.return_value.id
    )


async def test_rejected_edit_announces_instead(cog, monkeypatch):
    config = make_config()
    channel = make_channel()
    response = SimpleNamespace(status=400, reason="Bad Request")
    channel.edit = AsyncMock(side_effect=discord.HTTPException(response, "nope"))
    wire(cog, monkeypatch, make_messages(10), make_pulse(summary="Wheels!"))

    assert await cog.process_channel(config, channel) == "announced"
    channel.send.assert_awaited_once_with("Wheels!")


async def test_stalled_edit_announces_instead(cog, monkeypatch):
    """discord.py sleeps through an exhausted bucket; the cog must not."""
    config = make_config()
    channel = make_channel()

    async def hang(**kwargs):
        await asyncio.sleep(60)

    channel.edit = hang
    monkeypatch.setattr(
        "cogs.trendingchannel.trendingchannel.EDIT_TIMEOUT_SECONDS", 0.01
    )
    wire(cog, monkeypatch, make_messages(10), make_pulse(summary="Wheels!"))

    assert await cog.process_channel(config, channel) == "announced"
    channel.send.assert_awaited_once_with("Wheels!")


async def test_no_permissions_at_all_is_skipped(cog, monkeypatch):
    config = make_config()
    channel = make_channel(manage_channels=False, send_messages=False)
    wire(cog, monkeypatch, make_messages(10), make_pulse())

    assert await cog.process_channel(config, channel) == "skipped"
    channel.send.assert_not_awaited()


async def test_model_failure_still_starts_cooldown(cog, monkeypatch):
    config = make_config()
    channel = make_channel()
    wire(cog, monkeypatch, make_messages(10), None)

    assert await cog.process_channel(config, channel) == "failed"
    channel.edit.assert_not_awaited()
    assert TrendingChannelConfig.get().last_updated_at is not None


# ---------------------------------------------------------------------------
# the loop


async def test_unavailable_channel_does_not_block_the_others(cog, monkeypatch):
    make_config(channel_id=CHANNEL_ID)
    make_config(channel_id=CHANNEL_ID + 1)
    good = make_channel()
    good.id = CHANNEL_ID + 1
    cog.bot.get_channel = lambda cid: good if cid == CHANNEL_ID + 1 else None
    monkeypatch.setattr(discord, "TextChannel", SimpleNamespace)
    wire(cog, monkeypatch, make_messages(10), make_pulse())

    await cog.update_channels.coro(cog)
    good.edit.assert_awaited_once()


async def test_raising_channel_does_not_block_the_others(cog, monkeypatch):
    make_config(channel_id=CHANNEL_ID)
    make_config(channel_id=CHANNEL_ID + 1)
    bad = make_channel()
    good = make_channel()
    good.id = CHANNEL_ID + 1
    cog.bot.get_channel = lambda cid: good if cid == CHANNEL_ID + 1 else bad
    monkeypatch.setattr(discord, "TextChannel", SimpleNamespace)
    fetch, _ = wire(cog, monkeypatch, make_messages(10), make_pulse())
    fetch.side_effect = [RuntimeError("boom"), make_messages(10)]

    await cog.update_channels.coro(cog)
    good.edit.assert_awaited_once()


# ---------------------------------------------------------------------------
# persistence


async def test_toggle_persists_across_instances(cog, monkeypatch):
    """The old cog kept enabled channels in a class-level list, lost on restart."""
    channel = make_channel()
    monkeypatch.setattr(discord, "TextChannel", SimpleNamespace)
    interaction = SimpleNamespace(
        channel=channel,
        user=SimpleNamespace(id=7),
        response=SimpleNamespace(send_message=AsyncMock()),
    )

    await cog.toggle.callback(cog, interaction)
    fresh = TrendingChannel(cog.bot)
    assert list(
        TrendingChannelConfig.select().where(
            TrendingChannelConfig.channel_id == channel.id
        )
    )
    assert fresh.bot.database is cog.bot.database

    await cog.toggle.callback(cog, interaction)
    assert TrendingChannelConfig.select().count() == 0


async def test_deleted_channel_is_forgotten(cog):
    make_config()
    await cog.on_guild_channel_delete(SimpleNamespace(id=CHANNEL_ID))
    assert TrendingChannelConfig.select().count() == 0
