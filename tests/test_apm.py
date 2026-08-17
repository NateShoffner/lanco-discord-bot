"""Tests for the Elastic APM instrumentation.

Elastic does the reporting, so what is worth pinning here is that the data
actually reaches it, correctly labelled. Two cases carry most of the value:

- a command rejected by a check must still produce a transaction. It never
  reaches ``before_invoke``, so nothing would otherwise be reported at all and
  a permission-gated command would look identical to an unused one;
- the registered inventory must be emitted, because APM only ever sees what
  ran and cannot otherwise distinguish a command nobody has invoked from one
  that does not exist.

The assertions run against a real ``elasticapm.Client`` with its transport
swapped for an in-memory one, so transaction names, types, results, and labels
are checked as the agent would actually serialize them.
"""

import os
import sys

import discord
import discord.ext.test as dpytest
import elasticapm
import pytest
import pytest_asyncio
from discord.ext import commands
from elasticapm.base import set_client

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from utils import apm


class RecordingClient(elasticapm.Client):
    """An APM client that keeps everything it would have sent."""

    def __init__(self):
        super().__init__(
            service_name="test",
            environment="test",
            # No server to talk to, and nothing should be sampled away or
            # batched out of reach of an assertion.
            transport_class="elasticapm.transport.base.Transport",
            metrics_interval="0ms",
            central_config="false",
            disable_send=True,
        )
        self.events = []

    def queue(self, event_type, data, flush=False):
        self.events.append((event_type, data))

    @property
    def transactions(self):
        return [data for kind, data in self.events if kind == "transaction"]

    @property
    def spans(self):
        return [data for kind, data in self.events if kind == "span"]

    def named(self, name):
        return [t for t in self.transactions if t.get("name") == name]


@pytest.fixture
def apm_client():
    # Constructing a Client registers it as the process-wide client, which is
    # exactly what utils.apm reaches for via get_client().
    client = RecordingClient()
    yield client
    client.close()
    set_client(None)


def labels_of(transaction) -> dict:
    return transaction.get("context", {}).get("tags", {})


class SampleCog(commands.Cog, name="Sample"):
    @commands.command(name="works")
    async def works(self, ctx):
        await ctx.send("ok")

    @commands.command(name="breaks")
    async def breaks(self, ctx):
        raise RuntimeError("boom")

    @commands.command(name="gated")
    @commands.check(lambda ctx: False)
    async def gated(self, ctx):  # pragma: no cover - the check always refuses
        await ctx.send("never")


@pytest_asyncio.fixture
async def bot(apm_client):
    from main import LancoBot

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    b = LancoBot(command_prefix=".", intents=intents, owner_id=1, max_messages=100)
    apm.install(b)

    # main's before/after_invoke hooks are bound to its module-level bot, so
    # they are re-registered here against the instance under test.
    @b.before_invoke
    async def _begin(ctx):
        apm.mark_invoked(ctx)
        apm_client.begin_transaction(apm.TX_COMMAND)
        apm.label(
            command=str(ctx.command),
            cog=ctx.cog.qualified_name if ctx.cog else None,
        )

    @b.after_invoke
    async def _end(ctx):
        result = apm.RESULT_FAILURE if ctx.command_failed else apm.RESULT_SUCCESS
        apm_client.end_transaction(str(ctx.command), result)

    @b.event
    async def on_command_error(ctx, error):
        pass

    await b._async_setup_hook()
    await b.add_cog(SampleCog())
    dpytest.configure(b)
    yield b
    await dpytest.empty_queue()


async def run(content: str, expect_error: bool = False):
    """Dispatch a message, tolerating an error dpytest re-raises afterwards."""
    try:
        await dpytest.message(content)
    except Exception:
        if not expect_error:
            raise


# --- activity --------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_command_is_reported(bot, apm_client):
    await run(".works")

    tx = apm_client.named("works")
    assert len(tx) == 1
    assert tx[0]["type"] == apm.TX_COMMAND
    assert tx[0]["result"] == apm.RESULT_SUCCESS
    assert labels_of(tx[0])["cog"] == "Sample"


@pytest.mark.asyncio
async def test_failing_command_is_reported_as_a_failure(bot, apm_client):
    await run(".breaks", expect_error=True)

    tx = apm_client.named("breaks")
    assert len(tx) == 1, "the command ran, so exactly one transaction is expected"
    assert tx[0]["result"] == apm.RESULT_FAILURE


@pytest.mark.asyncio
async def test_command_blocked_by_a_check_is_still_reported(bot, apm_client):
    """The case before_invoke never sees, so nothing else would report it."""
    await run(".gated", expect_error=True)

    tx = apm_client.named("gated")
    assert len(tx) == 1
    assert tx[0]["type"] == apm.TX_COMMAND
    assert tx[0]["result"] == apm.RESULT_DENIED
    assert labels_of(tx[0])["error_type"] == "CheckFailure"


@pytest.mark.asyncio
async def test_unknown_commands_are_not_reported(bot, apm_client):
    await run(".notacommand", expect_error=True)

    assert apm_client.transactions == []


@pytest.mark.asyncio
async def test_ordinary_messages_are_not_reported(bot, apm_client):
    await run("just chatting")

    assert apm_client.transactions == []


@pytest.mark.asyncio
async def test_cog_activity_helper_labels_the_cog(bot, apm_client):
    from cogs.lancocog import LancoCog

    class Helper(LancoCog, name="Helper"):
        pass

    Helper(bot).record_activity("scheduled_post", guild_id=42)

    tx = apm_client.named("scheduled_post")
    assert len(tx) == 1
    assert tx[0]["type"] == apm.TX_COG_ACTION
    assert labels_of(tx[0]) == {"cog": "Helper", "guild_id": "42"}


@pytest.mark.asyncio
async def test_transaction_context_manager_reports_failure_and_reraises(apm_client):
    with pytest.raises(RuntimeError):
        async with apm.transaction("intent", apm.TX_ROUTER_INTENT, cog="Some"):
            raise RuntimeError("boom")

    tx = apm_client.named("intent")
    assert len(tx) == 1
    assert tx[0]["type"] == apm.TX_ROUTER_INTENT
    assert tx[0]["result"] == apm.RESULT_FAILURE


# --- inventory -------------------------------------------------------------


@pytest.mark.asyncio
async def test_inventory_reports_registered_commands_and_cogs(bot, apm_client):
    from cogs.lancocog import LancoCog

    class Quiet(LancoCog, name="Quiet"):
        pass

    await bot.add_cog(Quiet(bot))

    count = apm.emit_inventory(bot)

    assert count > 0
    names = {span["name"] for span in apm_client.spans}
    # A command that has never been invoked, and a cog with no commands at all,
    # both have to appear: that is the entire point of emitting this.
    assert {"works", "breaks", "gated", "Quiet"} <= names

    inventory = apm_client.named("registered")
    assert inventory, "inventory spans must hang off an inventory transaction"
    assert all(tx["type"] == apm.TX_INVENTORY for tx in inventory)


@pytest.mark.asyncio
async def test_inventory_chunks_stay_within_the_span_limit(
    bot, apm_client, monkeypatch
):
    monkeypatch.setattr(apm, "INVENTORY_CHUNK", 2)

    apm.emit_inventory(bot)

    per_transaction = {}
    for span in apm_client.spans:
        per_transaction[span["transaction_id"]] = (
            per_transaction.get(span["transaction_id"], 0) + 1
        )
    assert per_transaction, "expected spans to be emitted"
    assert max(per_transaction.values()) <= 2


# --- classification --------------------------------------------------------


def test_result_classification():
    assert apm.result_for(None) == apm.RESULT_SUCCESS
    assert apm.result_for(commands.MissingPermissions([])) == apm.RESULT_DENIED
    assert apm.result_for(commands.BadArgument("nope")) == apm.RESULT_DENIED
    assert apm.result_for(RuntimeError("boom")) == apm.RESULT_FAILURE


def test_error_type_unwraps_the_original():
    wrapped = commands.CommandInvokeError(ValueError("inner"))
    assert apm.error_type_of(wrapped) == "ValueError"
    assert apm.error_type_of(None) is None


def test_everything_is_a_noop_without_a_client():
    """APM is optional, so the bot must behave identically with it off."""
    set_client(None)
    apm.record(apm.TX_COG_ACTION, "anything", cog="Nobody")
    apm.label(cog="Nobody")
    assert apm.emit_inventory(object()) == 0
