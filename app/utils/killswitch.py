"""Owner's emergency stop. See the Killswitch section of CLAUDE.md.

Engaged, the bot stays connected but drops every gateway event, app command,
component, and loop iteration. Only the killswitch command still works. The
state is persisted so a restart cannot re-arm a bot the owner switched off.
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

COMMAND_NAME = "killswitch"
REFUSAL_TEXT = "The bot is currently switched off by its owner."

# Gateway plumbing and command bookkeeping still pass while engaged. "message"
# is deliberately absent: LancoBot.dispatch routes it to the command parser only.
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
        "command",
        "command_completion",
        "command_error",
        "app_command_completion",
    }
)


class KillswitchState(BaseModel):
    id = IntegerField(primary_key=True)
    engaged = BooleanField(default=False)
    engaged_by = BigIntegerField(null=True)
    engaged_at = DateTimeField(null=True)
    reason = TextField(null=True)

    class Meta:
        table_name = "killswitch"


ROW_ID = 1


def is_exempt_command(command) -> bool:
    """The killswitch command or one of its subcommands, on either tree."""
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
        self.dropped: Counter[str] = Counter()  # refusals by kind since engage
        self._saved_presence: Optional[tuple[discord.Status, object]] = None

    @property
    def engaged(self) -> bool:
        return self._engaged

    def load(self) -> None:
        KillswitchState.create_table(safe=True)
        row = KillswitchState.get_or_none(KillswitchState.id == ROW_ID)
        if row is None:
            return
        self._engaged = bool(row.engaged)
        self.engaged_by = row.engaged_by
        self.engaged_at = row.engaged_at
        self.reason = row.reason
        if self._engaged:
            logger.warning(
                "Killswitch is ENGAGED (by %s at %s, reason: %s): ignoring "
                "everything except the %s command",
                self.engaged_by,
                self.engaged_at,
                self.reason or "none given",
                COMMAND_NAME,
            )

    def _persist(self) -> None:
        KillswitchState.insert(
            id=ROW_ID,
            engaged=self._engaged,
            engaged_by=self.engaged_by,
            engaged_at=self.engaged_at,
            reason=self.reason,
        ).on_conflict_replace().execute()

    async def engage(self, user_id: int, reason: Optional[str] = None) -> bool:
        """Returns False if already engaged."""
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
        """Returns False if not engaged."""
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

    # Gates. dispatch runs for every gateway event, so none of these may touch
    # the database.

    def allows_event(self, event: str) -> bool:
        if not self._engaged or event in PASSTHROUGH_EVENTS:
            return True
        self.dropped[event] += 1
        return False

    def allows_command(self, command) -> bool:
        if not self._engaged or is_exempt_command(command):
            return True
        self.dropped["command"] += 1
        return False

    def allows_interaction(self, interaction: discord.Interaction) -> bool:
        """Refuses with an ephemeral notice: an unanswered slash command
        renders as "This interaction failed", which reads as a bug."""
        if not self._engaged or is_exempt_command(interaction.command):
            return True
        self.dropped["app_command"] += 1
        if interaction.type is discord.InteractionType.application_command:
            self.refuse_interaction(interaction)
        return False

    def refuse_component(self, interaction: Optional[discord.Interaction]) -> None:
        self.dropped["component"] += 1
        if interaction is not None:
            self.refuse_interaction(interaction)

    def allows_loop_iteration(self) -> bool:
        if not self._engaged:
            return True
        self.dropped["loop"] += 1
        return False

    def refuse_interaction(self, interaction: discord.Interaction) -> None:
        """Best effort, from sync code: a refusal must not become a new failure."""

        async def respond():
            try:
                await interaction.response.send_message(REFUSAL_TEXT, ephemeral=True)
            except Exception:
                logger.debug("Could not answer refused interaction", exc_info=True)

        try:
            asyncio.get_running_loop().create_task(respond())
        except RuntimeError:
            pass

    async def apply_presence(self) -> None:
        """DND while engaged, the previous presence otherwise. Also called from
        on_ready, since presence does not survive a reconnect."""
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
        # guild.me carries the live presence; Client.activity is only the
        # identify-time value.
        for guild in self.bot.guilds:
            if guild.me is not None:
                return (guild.me.status, guild.me.activity)
        return (discord.Status.online, None)

    def build_status_embed(self, footer: Optional[str] = None) -> discord.Embed:
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
                    name="Since", value=f"<t:{int(self.engaged_at.timestamp())}:R>"
                )
            embed.add_field(name="Reason", value=self.reason or "none given")
            if self.dropped:
                top = ", ".join(f"{k}: {n}" for k, n in self.dropped.most_common(5))
                embed.add_field(
                    name=f"Dropped ({sum(self.dropped.values())})",
                    value=top,
                    inline=False,
                )
        else:
            embed = discord.Embed(
                title="Killswitch: off",
                description="The bot is running normally.",
                color=discord.Color.green(),
            )
        if footer:
            embed.set_footer(text=footer)
        return embed
