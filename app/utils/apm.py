"""Elastic APM instrumentation. Kibana does the reporting; this feeds it.

*Activity* - commands, router intents, and embed fixes become labelled
transactions. Commands would produce them anyway; a routed cog or an embed
fixer never runs a command, so its work would otherwise be invisible.

*Inventory* - the commands and cogs the bot registers, emitted once per
process. APM only ever sees what ran, so without it a command nobody has
invoked is indistinguishable from one that does not exist.

The client is built in ``main.init_apm``; everything here reaches it via
``elasticapm.get_client()`` and no-ops when APM is unconfigured.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

import discord
import elasticapm
from discord.ext import commands

logger = logging.getLogger(__name__)

# Transaction types. Dashboards filter on these, so renaming one breaks saved
# Kibana queries.
TX_COMMAND = "command"
TX_APP_COMMAND = "app_command"
TX_ROUTER_INTENT = "router_intent"
TX_EMBED_FIX = "embed_fix"
TX_COG_ACTION = "cog_action"
TX_INVENTORY = "inventory"

RESULT_SUCCESS = "success"
RESULT_FAILURE = "failure"
#: A check refused it. Not a failure, and not the same as unused: a command
#: nobody may run is a different problem from one that is broken.
RESULT_DENIED = "denied"

#: The agent silently drops spans past ``transaction_max_spans`` (500), and a
#: truncated inventory reads as "these commands do not exist".
INVENTORY_CHUNK = 200

_TRANSACTION_ATTR = "_apm_transaction"
#: Where the app command error handler parks the exception for the tree.
ERROR_EXTRA = "apm_error"

#: Rejected before running rather than broken.
_DENIED_ERRORS = (
    commands.CheckFailure,
    commands.CommandOnCooldown,
    commands.DisabledCommand,
    commands.UserInputError,
    discord.app_commands.CheckFailure,
    discord.app_commands.CommandOnCooldown,
)


def client():
    return elasticapm.get_client()


def result_for(error: Optional[BaseException]) -> str:
    if error is None:
        return RESULT_SUCCESS
    if isinstance(error, _DENIED_ERRORS):
        return RESULT_DENIED
    return RESULT_FAILURE


def error_type_of(error: Optional[BaseException]) -> Optional[str]:
    """The underlying exception's name, unwrapping discord.py's wrapper."""
    if error is None:
        return None
    return type(getattr(error, "original", error)).__name__


def label(**labels) -> None:
    """Label the in-flight transaction. Safe with no transaction active."""
    if client() is None:
        return
    try:
        elasticapm.label(**{k: str(v) for k, v in labels.items() if v is not None})
    except Exception:
        logger.debug("Failed to label APM transaction", exc_info=True)


@asynccontextmanager
async def transaction(name: str, tx_type: str, **labels):
    """Wrap a block in a transaction, so spans inside it are captured too.

    For work already finished by the time it is known about, use :func:`record`.
    """
    apm = client()
    if apm is None:
        yield
        return
    apm.begin_transaction(tx_type)
    label(**labels)
    try:
        yield
    except Exception:
        apm.end_transaction(name, RESULT_FAILURE)
        raise
    else:
        apm.end_transaction(name, RESULT_SUCCESS)


def record(tx_type: str, name: str, *, result: str = RESULT_SUCCESS, **labels) -> None:
    """Report something that has already happened, for work that cannot be
    bracketed. Never raises: bookkeeping must not become a new failure mode.
    """
    apm = client()
    if apm is None:
        return
    try:
        apm.begin_transaction(tx_type)
        label(**labels)
        apm.end_transaction(name, result)
    except Exception:
        logger.debug("Failed to record %s transaction", tx_type, exc_info=True)


def app_command_cog(command) -> Optional[str]:
    binding = getattr(command, "binding", None)
    return binding.qualified_name if binding else None


# --- dispatch wiring -------------------------------------------------------


def install(bot) -> None:
    """Report prefix commands rejected before they ever ran.

    A refused command never reaches ``before_invoke``, so no transaction opens
    and nothing reaches Elastic, leaving a gated command indistinguishable from
    a dead one. A listener because the invoke hooks are single-slot and already
    bracket the command itself.
    """

    async def on_command_error(ctx: commands.Context, error: Exception):
        if isinstance(error, commands.CommandNotFound) or ctx.command is None:
            return
        if getattr(ctx, _TRANSACTION_ATTR, False):
            return  # it ran, so after_invoke already closed its transaction
        record(
            TX_COMMAND,
            ctx.command.qualified_name,
            result=result_for(error),
            command=ctx.command.qualified_name,
            cog=ctx.cog.qualified_name if ctx.cog else None,
            guild_id=ctx.guild.id if ctx.guild else None,
            error_type=error_type_of(error),
        )

    bot.add_listener(on_command_error, "on_command_error")


def mark_invoked(ctx: commands.Context) -> None:
    """Record that before_invoke opened a transaction for this context."""
    setattr(ctx, _TRANSACTION_ATTR, True)


# --- inventory -------------------------------------------------------------


def command_inventory(bot) -> list[dict]:
    """Every command the bot currently registers, as (kind, cog, name)."""
    inventory: list[dict] = []

    for command in bot.walk_commands():
        inventory.append(
            {
                "kind": TX_COMMAND,
                "cog": command.cog.qualified_name if command.cog else "",
                "name": command.qualified_name,
            }
        )

    for command in bot.tree.walk_commands():
        if isinstance(command, discord.app_commands.Group):
            continue
        inventory.append(
            {
                "kind": TX_APP_COMMAND,
                "cog": app_command_cog(command) or "",
                "name": command.qualified_name,
            }
        )

    for menu_type in (discord.AppCommandType.user, discord.AppCommandType.message):
        for command in bot.tree.get_commands(type=menu_type):
            inventory.append({"kind": TX_APP_COMMAND, "cog": "", "name": command.name})

    return inventory


def emit_inventory(bot) -> int:
    """Report the registered commands and cogs as one span each, returning the
    count.

    Spans rather than transactions: a few hundred transactions per restart
    would distort the service's throughput charts. In Kibana the registered set
    is ``transaction.type: inventory`` and the used set is everything else;
    what appears in the first and not the second is the retirement shortlist.
    """
    apm = client()
    if apm is None:
        return 0

    entries = command_inventory(bot)
    entries += [
        {"kind": "cog", "cog": cog.get_cog_name(), "name": cog.get_cog_name()}
        for cog in bot.get_lanco_cogs()
    ]

    try:
        for start in range(0, len(entries), INVENTORY_CHUNK):
            chunk = entries[start : start + INVENTORY_CHUNK]
            apm.begin_transaction(TX_INVENTORY)
            for entry in chunk:
                with elasticapm.capture_span(
                    name=entry["name"],
                    span_type=TX_INVENTORY,
                    labels={"kind": entry["kind"], "cog": entry["cog"]},
                ):
                    pass
            apm.end_transaction("registered", RESULT_SUCCESS)
    except Exception:
        logger.warning("Failed to emit APM inventory", exc_info=True)
        return 0

    logger.info(f"Reported {len(entries)} registered command(s) and cog(s) to APM")
    return len(entries)
