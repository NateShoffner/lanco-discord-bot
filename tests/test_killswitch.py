"""The owner's killswitch must stop everything except itself: gateway events,
app commands, components, and loops are all gated, and the state survives a
restart."""

import asyncio
import os
import sys

os.environ.setdefault("BOT_ENV", "test")
os.environ.setdefault("DB_TYPE", "sqlite")
os.environ.setdefault("SQLITE_DB", ":memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import discord
import discord.ext.test as dpytest
import pytest
import pytest_asyncio
from cogs.lancocog import LancoCog
from db import database_proxy
from discord.ext import commands, tasks
from utils.killswitch import Killswitch, is_exempt_command

from tests.test_bot import test_db  # noqa: F401  (autouse fixture)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def bot(test_db):
    """LancoBot with the killswitch commands and global check; member 0 is the
    owner."""
    import main
    from main import BlacklistedUser, LancoBot

    database_proxy.initialize(test_db)
    test_db.create_tables([BlacklistedUser])

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    b = LancoBot(command_prefix=".", intents=intents, owner_id=1, max_messages=100)
    b.database = test_db
    b.add_command(main.killswitch_status)
    b.add_check(main.global_block_check)
    await b._async_setup_hook()
    dpytest.configure(b, members=2)
    b.owner_id = dpytest.get_config().members[0].id

    # dpytest re-raises command errors; a refused check is the expected outcome
    async def on_command_error(ctx, error):
        if not isinstance(error, commands.CheckFailure):
            raise error

    b.event(on_command_error)
    yield b
    for cog in list(b.cogs.values()):
        await b.remove_cog(cog.qualified_name)
    await dpytest.empty_queue()


class _ListenerCog(LancoCog, name="ListenerCog"):
    def __init__(self, bot):
        super().__init__(bot)
        self.seen = []

    @commands.Cog.listener()
    async def on_message(self, message):
        self.seen.append(message.content)

    @commands.command(name="echo")
    async def echo(self, ctx, *, text: str):
        await ctx.send(text)


async def _settle():
    for _ in range(5):
        await asyncio.sleep(0.01)


def _owner():
    return dpytest.get_config().members[0]


def _other():
    return dpytest.get_config().members[1]


async def test_engaged_drops_events_but_the_switch_still_works(bot):
    cog = _ListenerCog(bot)
    await bot.add_cog(cog)

    await dpytest.message("before", member=_owner())
    await _settle()
    assert cog.seen == ["before"]

    # the engaging message is dispatched normally: the switch was off on arrival
    await dpytest.message(".killswitch on spam in general", member=_owner())
    await _settle()
    assert bot.killswitch.engaged
    assert bot.killswitch.reason == "spam in general"
    assert cog.seen == ["before", ".killswitch on spam in general"]

    await dpytest.message("during", member=_other())
    await dpytest.message(".echo hello", member=_other())
    await _settle()
    assert cog.seen[-1] != ".echo hello", "a listener saw a message while engaged"
    assert "during" not in cog.seen
    assert bot.killswitch.dropped["message"] >= 2
    assert bot.killswitch.dropped["command"] == 1

    await dpytest.message(".killswitch off", member=_owner())
    await _settle()
    assert not bot.killswitch.engaged
    assert ".killswitch off" not in cog.seen

    await dpytest.message("after", member=_owner())
    await _settle()
    assert cog.seen[-1] == "after"


async def test_only_the_owner_can_switch(bot):
    await dpytest.message(".killswitch on", member=_other())
    await _settle()
    assert not bot.killswitch.engaged

    await bot.killswitch.engage(_owner().id)
    await dpytest.message(".killswitch off", member=_other())
    await _settle()
    assert bot.killswitch.engaged


async def test_a_message_listener_is_not_scheduled_while_engaged(bot):
    seen = []

    async def listener(message):
        seen.append(message.content)

    bot.add_listener(listener, "on_message")
    await bot.killswitch.engage(1)

    await dpytest.message("hi", member=_other())
    await _settle()
    assert seen == []


def test_passthrough_is_limited_to_plumbing(bot):
    ks = Killswitch(bot)
    ks._engaged = True
    for event in ("ready", "resumed", "disconnect", "command_error"):
        assert ks.allows_event(event), event
    for event in (
        "message",
        "message_edit",
        "reaction_add",
        "member_join",
        "interaction",
        "typing",
        "presence_update",
    ):
        assert not ks.allows_event(event), event
    assert ks.dropped["message"] == 1


class _FakeResponse:
    def __init__(self):
        self.sent = []

    async def send_message(self, content, **kwargs):
        self.sent.append((content, kwargs))


class _FakeInteraction:
    def __init__(
        self, bot, command=None, kind=discord.InteractionType.application_command
    ):
        self.client = bot
        self.user = type("User", (), {"id": 999})()
        self.command = command
        self.type = kind
        self.extras = {}
        self.response = _FakeResponse()


async def _noop_app_command(interaction: discord.Interaction):
    pass


async def test_interaction_check_refuses_everything_but_the_switch(bot):
    import main
    from main import InstrumentedCommandTree

    await bot.killswitch.engage(1)

    other = discord.app_commands.Command(
        name="weather", description="x", callback=_noop_app_command
    )
    refused = _FakeInteraction(bot, command=other)
    assert await InstrumentedCommandTree.interaction_check(None, refused) is False
    assert isinstance(
        refused.extras[main.apm.ERROR_EXTRA], discord.app_commands.CheckFailure
    )
    await _settle()
    assert refused.response.sent and refused.response.sent[0][1]["ephemeral"] is True

    allowed = _FakeInteraction(bot, command=main.killswitch_slash)
    assert await InstrumentedCommandTree.interaction_check(None, allowed) is True
    assert allowed.response.sent == []


async def test_autocomplete_is_refused_silently(bot):
    await bot.killswitch.engage(1)
    interaction = _FakeInteraction(bot, kind=discord.InteractionType.autocomplete)
    assert not bot.killswitch.allows_interaction(interaction)
    await _settle()
    assert interaction.response.sent == []


def test_subcommands_of_the_switch_are_exempt():
    import main

    assert is_exempt_command(main.killswitch_status)
    assert is_exempt_command(main.killswitch_on)
    assert is_exempt_command(main.killswitch_off)
    assert is_exempt_command(main.killswitch_slash)
    assert not is_exempt_command(main.guildsync)
    assert not is_exempt_command(None)


async def test_components_are_gated_at_the_view_store(bot):
    store = bot._connection._view_store
    calls = []
    store.dispatch_view = lambda *a: calls.append(("view", a))
    store.dispatch_modal = lambda *a: calls.append(("modal", a))
    bot._gate_components()

    interaction = _FakeInteraction(bot, kind=discord.InteractionType.component)

    store.dispatch_view(2, "custom", interaction)
    assert len(calls) == 1

    await bot.killswitch.engage(1)
    store.dispatch_view(2, "custom", interaction)
    store.dispatch_modal("custom", interaction, [], {})
    assert len(calls) == 1, "a component reached its view while engaged"
    assert bot.killswitch.dropped["component"] == 2

    await bot.killswitch.disengage(1)
    store.dispatch_modal("custom", interaction, [], {})
    assert len(calls) == 2


class _StubBot:
    def __init__(self):
        self.killswitch = Killswitch(self)
        self.killswitch.load()
        self.guilds = []

    async def wait_until_ready(self):
        pass


class _LoopCog(LancoCog, name="KillswitchLoopCog"):
    def __init__(self, bot):
        super().__init__(bot)
        self.iterations = 0

    @tasks.loop(seconds=0.01)
    async def ticker(self):
        self.iterations += 1


async def test_loops_skip_iterations_while_engaged():
    stub = _StubBot()
    cog = _LoopCog(stub)
    cog.start_loop(cog.ticker)
    try:
        await asyncio.sleep(0.1)
        assert cog.iterations > 0

        await stub.killswitch.engage(1)
        await asyncio.sleep(0.02)
        at_engage = cog.iterations
        await asyncio.sleep(0.1)
        assert cog.iterations == at_engage, "the loop kept working while engaged"
        assert stub.killswitch.dropped["loop"] > 0
        assert cog.ticker.is_running(), "the loop was cancelled, not paused"

        await stub.killswitch.disengage(1)
        await asyncio.sleep(0.1)
        assert cog.iterations > at_engage
    finally:
        cog.ticker.cancel()


async def test_state_survives_a_restart(bot):
    await bot.killswitch.engage(42, "bad deploy")

    fresh = Killswitch(bot)
    fresh.load()
    assert fresh.engaged
    assert fresh.engaged_by == 42
    assert fresh.reason == "bad deploy"
    assert fresh.engaged_at is not None

    await fresh.disengage(42)
    again = Killswitch(bot)
    again.load()
    assert not again.engaged


async def test_switching_is_idempotent(bot):
    assert await bot.killswitch.engage(1) is True
    assert await bot.killswitch.engage(1) is False
    assert await bot.killswitch.disengage(1) is True
    assert await bot.killswitch.disengage(1) is False
