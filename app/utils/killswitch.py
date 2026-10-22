"""Global killswitch: one lever that stops the bot doing anything.

Engaged, the bot stays connected to the gateway but goes inert. Every message,
reaction, member event, slash command, button, modal, and background loop is
dropped on the floor, and the only thing that still works is the command that
disengages it. The point is to have something the owner can reach for in the
first minute of an incident (a cog spamming a channel, a leaked key, a model
returning garbage) that is faster and safer than finding the host and stopping
the container.

Why gate centrally instead of unloading cogs: unloading is destructive (cog
state goes, and a cog that fails to come back leaves the bot half-restored),
and it still does nothing about the core commands in main. Gating sits in the
few places every piece of functionality has to pass through:

- ``LancoBot.dispatch`` for gateway events, which covers every listener, the
  router, and the URL embed handlers.
- ``InstrumentedCommandTree.interaction_check`` for slash commands and context
  menus, which never go through ``dispatch``.
- The view store for buttons, selects, and modals, which also bypass it.
- ``LancoCog.start_loop`` for background loops, which skip their iteration
  rather than being cancelled, so nothing needs restarting on the way back.

The state is persisted. A deploy or a crash loop recreates the container, and a
restart silently re-arming a bot the owner deliberately switched off would be
the worst possible behaviour for an emergency control.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from collections import Counter
from typing import TYPE_CHECKING, Optional

import discord
from db import BaseModel
from peewee import BigIntegerField, BooleanField, DateTimeField, IntegerField, TextField

if TYPE_CHECKING:
    from main import LancoBot

logger = logging.getLogger(__name__)

#: Name of the prefix command and the slash command. The gate exempts a
#: command whose root has this name, so subcommands (``.killswitch off``)
#: pass too.
COMMAND_NAME = "killswitch"

#: What a refused slash command or component is told. Static text: the bot
#: must not do work on behalf of a refused interaction.
REFUSAL_TEXT = "The bot is currently switched off by its owner."

#: Events that still reach listeners while engaged. Everything here is either
#: gateway bookkeeping with no user-facing effect, or part of the command
#: lifecycle that the disengage command needs. ``message`` is deliberately
#: absent: the bot's own ``on_message`` is scheduled directly so the command
#: parser still runs, but no listener sees the message.
PASSTHROUGH_EVENTS = frozenset(
    {
        "connect",
        "disconnect",
        "resumed",
        "ready",
        "shard_connect",
        "shard_disconnect",
        "shard_resumed",
        "shard_ready",
        "socket_event_type",
        "socket_raw_receive",
        "socket_raw_send",
        "error",
        # command_error is how a refused prefix command reaches APM as denied
        "command",
        "command_completion",
        "command_error",
        "app_command_completion",
    }
)


class KillswitchState(BaseModel):
    """Single-row table. ``id`` is always ``ROW_ID``."""

    id = IntegerField(primary_key=True)
    engaged = BooleanField(default=False)
    engaged_by = BigIntegerField(null=True)
    engaged_at = DateTimeField(null=True)
    reason = TextField(null=True)

    class Meta:
        table_name = "killswitch"


ROW_ID = 1


def is_exempt_command(command) -> bool:
    """True for the killswitch command or any of its subcommands, on either
    the prefix tree or the app command tree.
    """
    if command is None:
        return False
    root = getattr(command, "root_parent", None) or command
    return getattr(root, "name", None) == COMMAND_NAME


class Killswitch:
    def __init__(self, bot: "LancoBot"):
        self.bot = bot
        self._engaged = False
        self.engaged_by: Optional[int] = None
        self.engaged_at: Optional[datetime.datetime] = None
        self.reason: Optional[str] = None
        #: What was refused since the switch was engaged, by kind: a gateway
        #: event name, ``app_command``, ``component``, or ``loop``. Reset on
        #: engage, so the status readout answers "what has it stopped".
        self.dropped: Counter[str] = Counter()
        self._saved_presence: Optional[tuple[discord.Status, object]] = None

    @property
    def engaged(self) -> bool:
        return self._engaged

    # --- persistence -----------------------------------------------------

    def load(self) -> None:
        """Create the table if needed and pick up the persisted state.

        Called once at construction. Logged at WARNING when engaged, because a
        bot that comes up inert and never says why is a confusing outage.
        """
        self._ensure_table()
        row = KillswitchState.get_or_none(KillswitchState.id == ROW_ID)
        if row is None:
            return
        self._engaged = bool(row.engaged)
        self.engaged_by = row.engaged_by
        self.engaged_at = row.engaged_at
        self.reason = row.reason
        if self._engaged:
            logger.warning(
                "Killswitch is ENGAGED (by %s at %s, reason: %s): the bot will "
                "ignore everything except the %s command",
                self.engaged_by,
                self.engaged_at,
                self.reason or "none given",
                COMMAND_NAME,
            )

    @staticmethod
    def _ensure_table() -> None:
        KillswitchState.create_table(safe=True)

    def _persist(self) -> None:
        self._ensure_table()
        KillswitchState.insert(
            id=ROW_ID,
            engaged=self._engaged,
            engaged_by=self.engaged_by,
            engaged_at=self.engaged_at,
            reason=self.reason,
        ).on_conflict_replace().execute()

    # --- switching -------------------------------------------------------

    async def engage(self, user_id: int, reason: Optional[str] = None) -> bool:
        """Switch off. Returns False if it was already engaged."""
        if self._engaged:
            return False
        self._engaged = True
        self.engaged_by = user_id
        self.engaged_at = datetime.datetime.now()
        self.reason = reason
        self.dropped.clear()
        self._persist()
        logger.warning(
            "Killswitch ENGAGED by %s (reason: %s)", user_id, reason or "none given"
        )
        await self.apply_presence()
        return True

    async def disengage(self, user_id: int) -> bool:
        """Switch back on. Returns False if it was not engaged."""
        if not self._engaged:
            return False
        self._engaged = False
        self._persist()
        logger.warning(
            "Killswitch disengaged by %s after dropping %d event(s)",
            user_id,
            sum(self.dropped.values()),
        )
        await self.apply_presence()
        return True

    # --- gates -----------------------------------------------------------
    #
    # Each gate is one attribute read on the hot path. ``dispatch`` runs for
    # every gateway event, so nothing here may touch the database.

    def allows_event(self, event: str) -> bool:
        if not self._engaged or event in PASSTHROUGH_EVENTS:
            return True
        self.note_dropped(event)
        return False

    def allows_command(self, command) -> bool:
        """Prefix command gate, for the global check."""
        if not self._engaged or is_exempt_command(command):
            return True
        self.note_dropped("command")
        return False

    def allows_interaction(self, interaction: discord.Interaction) -> bool:
        """App command gate, for the tree's interaction_check. Refuses with an
        ephemeral notice rather than silently, because an unanswered slash
        command renders as "This interaction failed", which reads as a bug.
        """
        if not self._engaged or is_exempt_command(interaction.command):
            return True
        self.note_dropped("app_command")
        if interaction.type is discord.InteractionType.application_command:
            self.refuse_interaction(interaction)
        return False

    def refuse_component(self, interaction: Optional[discord.Interaction]) -> None:
        """Record a dropped button, select, or modal, and tell the user if the
        view store wrapper managed to find the interaction among its arguments.
        """
        self.note_dropped("component")
        if interaction is not None:
            self.refuse_interaction(interaction)

    def allows_loop_iteration(self, name: str) -> bool:
        if not self._engaged:
            return True
        self.note_dropped("loop")
        logger.debug("Killswitch engaged, skipping loop iteration %s", name)
        return False

    def note_dropped(self, kind: str) -> None:
        self.dropped[kind] += 1

    def refuse_interaction(self, interaction: discord.Interaction) -> None:
        """Answer a refused interaction from sync code. Best effort: the
        refusal must never become a new failure mode.
        """

        async def respond():
            try:
                await interaction.response.send_message(REFUSAL_TEXT, ephemeral=True)
            except Exception:
                logger.debug("Could not answer refused interaction", exc_info=True)

        try:
            asyncio.get_running_loop().create_task(respond())
        except RuntimeError:
            logger.debug("No running loop to answer refused interaction")

    # --- presence --------------------------------------------------------

    async def apply_presence(self) -> None:
        """Show the state on the bot's profile: DND with a "killswitch engaged"
        activity while engaged, and whatever it was before when disengaged.
        Called on switch and from on_ready, since presence is not persisted
        across a reconnect. Failure here is logged and otherwise ignored; the
        switch itself has already flipped.
        """
        try:
            if self._engaged:
                if self._saved_presence is None:
                    self._saved_presence = self._current_presence()
                await self.bot.change_presence(
                    status=discord.Status.dnd,
                    activity=discord.Game(name="killswitch engaged"),
                )
            else:
                status, activity = self._saved_presence or (discord.Status.online, None)
                self._saved_presence = None
                await self.bot.change_presence(status=status, activity=activity)
        except Exception:
            logger.warning("Failed to update presence for killswitch", exc_info=True)

    def _current_presence(self) -> tuple[discord.Status, object]:
        # Client.activity is the identify-time value, not what /activity set
        # later; the member object in any guild carries the live presence.
        for guild in self.bot.guilds:
            me = guild.me
            if me is not None:
                return (me.status, me.activity)
        return (discord.Status.online, None)

    # --- reporting -------------------------------------------------------

    def build_status_embed(self) -> discord.Embed:
        if self._engaged:
            embed = discord.Embed(
                title="Killswitch: ENGAGED",
                description="The bot is ignoring everything except this command.",
                color=discord.Color.red(),
            )
            embed.add_field(
                name="Engaged by",
                value=f"<@{self.engaged_by}>" if self.engaged_by else "unknown",
            )
            if self.engaged_at:
                embed.add_field(
                    name="Since",
                    value=f"<t:{int(self.engaged_at.timestamp())}:R>",
                )
            embed.add_field(name="Reason", value=self.reason or "none given")
            total = sum(self.dropped.values())
            if total:
                top = ", ".join(
                    f"{kind}: {count}" for kind, count in self.dropped.most_common(5)
                )
                embed.add_field(name=f"Dropped ({total})", value=top, inline=False)
        else:
            embed = discord.Embed(
                title="Killswitch: off",
                description="The bot is running normally.",
                color=discord.Color.green(),
            )
        return embed
