"""
TrendingChannel Cog

Description:
A channel whose name and topic follow the conversation. The cog periodically
reads recent messages, asks the model what the channel is about right now,
and edits the channel name and topic to match. When it cannot edit the channel
(no Manage Channels permission, Discord's edit bucket is exhausted, or the
edit is rejected) it posts the model's summary as a message instead.
"""

import asyncio
import datetime
import os
import re

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands, tasks
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from utils.ai_utils import run_agent
from utils.command_utils import is_bot_owner_or_admin
from utils.message_utils import get_user_messages

from .models import TrendingChannelConfig

MODEL = "openai:gpt-5-nano"

# how often the loop checks whether any channel is due
POLL_INTERVAL_SECONDS = 60

# Discord allows two name or topic edits per channel per ten minutes, and
# discord.py sleeps on an exhausted bucket rather than failing. One update
# per five minutes keeps this cog inside the bucket on its own; the edit
# timeout below covers the case where someone else used it up.
UPDATE_COOLDOWN = datetime.timedelta(minutes=5)
EDIT_TIMEOUT_SECONDS = 15

# user messages that must arrive between analyses, so a single message does
# not trigger a paid model call and a rename
MIN_NEW_MESSAGES = 5
# how much recent history the model sees
HISTORY_LIMIT = 50

CHANNEL_NAME_MAX = 100
CHANNEL_TOPIC_MAX = 1024
ANNOUNCEMENT_MAX = 2000

SYSTEM_PROMPT = """
You watch a Discord channel and describe what people are talking about right now.
You will be given a transcript of recent messages in chronological order, one per line as @User: message.
Weight the most recent messages most heavily. Ignore bot commands, greetings, and off-topic noise.
Return:
- topics: the main topics being discussed, most prominent first
- channel_name: a channel name capturing the current discussion. Two to four words, lowercase,
  hyphen-separated, letters, digits and hyphens only, no stopwords, no spaces
- channel_topic: one friendly sentence describing what is being discussed, under 200 characters
- announcement: one to three friendly sentences summarizing the discussion for someone who just
  opened the channel. Do not mention that you are a bot or that you analyzed anything.
"""


class ChannelPulse(BaseModel):
    topics: list[str] = Field(
        ..., description="The main topics being discussed, most prominent first"
    )
    channel_name: str = Field(
        ...,
        description=(
            "A channel name capturing the current discussion: two to four words, "
            "lowercase, hyphen-separated, letters, digits and hyphens only, no stopwords"
        ),
    )
    channel_topic: str = Field(
        ...,
        description="One sentence describing what is being discussed, under 200 characters",
    )
    announcement: str = Field(
        ...,
        description=(
            "One to three friendly sentences summarizing the discussion for someone "
            "who just opened the channel"
        ),
    )


def sanitize_channel_name(name: str) -> str:
    """Coerce a model-suggested name into something Discord will accept.

    Discord lowercases and hyphenates text channel names itself, but rejects
    names over 100 characters outright, and the model is only asked nicely
    for the right shape. An empty result means the caller should keep the
    current name.
    """
    name = name.lower().strip()
    name = re.sub(r"[\s_]+", "-", name)
    name = re.sub(r"[^a-z0-9-]", "", name)
    name = re.sub(r"-{2,}", "-", name).strip("-")
    return name[:CHANNEL_NAME_MAX].rstrip("-")


def _utcnow() -> datetime.datetime:
    # naive UTC, matching how the other cogs store DateTimeField values in SQLite
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class TrendingChannel(
    LancoCog,
    name="TrendingChannel",
    description="Renames a channel and updates its topic to follow the conversation",
):
    g = app_commands.Group(
        name="trending",
        description="Trending channel commands",
        guild_only=True,
    )

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self._agent: Agent | None = None

    @property
    def agent(self) -> Agent:
        # built on first use so the cog can be constructed without a key in tests
        if self._agent is None:
            self._agent = Agent(
                model=MODEL,
                system_prompt=SYSTEM_PROMPT,
                output_type=ChannelPulse,
            )
        return self._agent

    async def cog_load(self):
        await super().cog_load()
        self.bot.database.create_tables([TrendingChannelConfig])
        self.update_channels.change_interval(seconds=POLL_INTERVAL_SECONDS)
        self.start_loop(self.update_channels)

    # ------------------------------------------------------------------
    # commands

    @g.command(
        name="toggle",
        description="Enable or disable trending updates for the current channel",
    )
    @is_bot_owner_or_admin()
    async def toggle(self, interaction: discord.Interaction):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "Trending updates only work in regular text channels.",
                ephemeral=True,
            )
            return

        config = TrendingChannelConfig.get_or_none(
            TrendingChannelConfig.channel_id == channel.id
        )
        if config is not None:
            config.delete_instance()
            await interaction.response.send_message(
                f"Trending updates disabled for {channel.mention}"
            )
            return

        TrendingChannelConfig.create(
            guild_id=channel.guild.id,
            channel_id=channel.id,
            enabled_by=interaction.user.id,
        )

        lines = [f"Trending updates enabled for {channel.mention}"]
        perms = channel.permissions_for(channel.guild.me)
        if not perms.manage_channels:
            lines.append(
                "I can't edit this channel (missing Manage Channels), "
                "so I'll post a summary message instead."
            )
        if not perms.manage_channels and not perms.send_messages:
            lines.append(
                "I can't post here either, so nothing will happen until one of "
                "those permissions is granted."
            )
        await interaction.response.send_message("\n".join(lines))

    @g.command(
        name="status",
        description="Show which channels have trending updates enabled",
    )
    @is_bot_owner_or_admin()
    async def status(self, interaction: discord.Interaction):
        configs = list(
            TrendingChannelConfig.select().where(
                TrendingChannelConfig.guild_id == interaction.guild.id
            )
        )
        if not configs:
            await interaction.response.send_message(
                "No channels have trending updates enabled.", ephemeral=True
            )
            return

        lines = []
        for config in configs:
            channel = interaction.guild.get_channel(config.channel_id)
            label = channel.mention if channel else f"`{config.channel_id}` (missing)"
            if config.last_updated_at:
                when = f"<t:{int(config.last_updated_at.replace(tzinfo=datetime.timezone.utc).timestamp())}:R>"
            else:
                when = "never"
            lines.append(f"{label}: last updated {when}")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @g.command(
        name="refresh",
        description="Analyze the current channel now instead of waiting for new messages",
    )
    @is_bot_owner_or_admin()
    async def refresh(self, interaction: discord.Interaction):
        channel = interaction.channel
        config = TrendingChannelConfig.get_or_none(
            TrendingChannelConfig.channel_id == channel.id
        )
        if config is None:
            await interaction.response.send_message(
                "Trending updates are not enabled here. Use `/trending toggle` first.",
                ephemeral=True,
            )
            return

        remaining = self.cooldown_remaining(config, _utcnow())
        if remaining:
            minutes = max(1, round(remaining.total_seconds() / 60))
            await interaction.response.send_message(
                f"This channel was updated recently. Try again in about {minutes} minute(s).",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        outcome = await self.process_channel(config, channel, force=True)
        messages = {
            "edited": "Channel name and topic updated.",
            "announced": "I couldn't edit the channel, so I posted a summary instead.",
            "unchanged": "The channel name and topic already match the discussion.",
            "no_messages": "There are no recent messages to analyze.",
            "failed": "The analysis failed. Check the logs for details.",
            "skipped": "I can neither edit this channel nor post in it.",
        }
        await interaction.followup.send(
            messages.get(outcome, "Nothing to do."), ephemeral=True
        )

    # ------------------------------------------------------------------
    # background work

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        deleted = (
            TrendingChannelConfig.delete()
            .where(TrendingChannelConfig.channel_id == channel.id)
            .execute()
        )
        if deleted:
            self.logger.info(
                f"Channel {channel.id} was deleted, trending config removed"
            )

    @tasks.loop(seconds=POLL_INTERVAL_SECONDS)
    async def update_channels(self):
        for config in list(TrendingChannelConfig.select()):
            channel = self.bot.get_channel(config.channel_id)
            if not isinstance(channel, discord.TextChannel):
                self.logger.warning(
                    f"Trending channel {config.channel_id} is unavailable, skipping"
                )
                continue
            # one bad channel must not stop the others
            try:
                await self.process_channel(config, channel)
            except Exception:
                self.logger.exception(f"Failed to update #{channel.name}")

    @staticmethod
    def cooldown_remaining(
        config: TrendingChannelConfig, now: datetime.datetime
    ) -> datetime.timedelta | None:
        if config.last_updated_at is None:
            return None
        elapsed = now - config.last_updated_at
        if elapsed >= UPDATE_COOLDOWN:
            return None
        return UPDATE_COOLDOWN - elapsed

    async def process_channel(
        self,
        config: TrendingChannelConfig,
        channel: discord.TextChannel,
        *,
        force: bool = False,
    ) -> str | None:
        """Analyze the channel if it is due and apply the result.

        Returns what happened ("edited", "announced", "unchanged",
        "no_messages", "failed", "skipped") or None when the channel was not
        due. ``force`` skips the new-message threshold but not the cooldown.
        """
        now = _utcnow()
        if self.cooldown_remaining(config, now):
            return None

        # cheap gate: nothing at all has been posted since the last look
        if not force and (
            channel.last_message_id is None
            or channel.last_message_id == config.last_seen_message_id
        ):
            return None

        messages = await get_user_messages(channel, limit=HISTORY_LIMIT)
        config.last_seen_message_id = channel.last_message_id
        config.save()

        if not messages:
            return "no_messages" if force else None

        new_messages = [
            m
            for m in messages
            if config.last_analyzed_message_id is None
            or m.id > config.last_analyzed_message_id
        ]
        if not force and len(new_messages) < MIN_NEW_MESSAGES:
            return None

        pulse = await self.analyze(messages)
        config.last_analyzed_message_id = max(m.id for m in messages)
        config.last_updated_at = now
        if pulse is None:
            config.save()
            return "failed"

        outcome = await self.apply(config, channel, pulse)
        config.save()
        return outcome

    async def analyze(self, messages: list[discord.Message]) -> ChannelPulse | None:
        # history arrives newest first; the model reads it in order
        lines = [
            f"@{m.author.display_name}: {m.content.strip()}" for m in reversed(messages)
        ]
        prompt = "TRANSCRIPT BEGIN\n" + "\n".join(lines) + "\nTRANSCRIPT END"
        result = await run_agent(lambda: self.agent.run(prompt))
        return result.output if result else None

    async def apply(
        self,
        config: TrendingChannelConfig,
        channel: discord.TextChannel,
        pulse: ChannelPulse,
    ) -> str:
        """Edit the channel to match the pulse, or announce it if that fails."""
        name = sanitize_channel_name(pulse.channel_name) or channel.name
        topic = pulse.channel_topic.strip()[:CHANNEL_TOPIC_MAX]

        changes = {}
        if name != channel.name:
            changes["name"] = name
        if topic and topic != (channel.topic or ""):
            changes["topic"] = topic
        if not changes:
            return "unchanged"

        perms = channel.permissions_for(channel.guild.me)
        if perms.manage_channels:
            try:
                # discord.py waits out an exhausted edit bucket rather than
                # raising, which would stall every other channel in the loop
                await asyncio.wait_for(
                    channel.edit(**changes, reason="Trending channel update"),
                    timeout=EDIT_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                self.logger.warning(
                    f"Editing #{channel.name} timed out (rate limited?), announcing instead"
                )
            except discord.HTTPException as e:
                self.logger.warning(f"Editing #{channel.name} failed: {e}")
            else:
                config.last_name = name
                config.last_topic = topic
                self.logger.info(f"Updated #{channel.name} -> #{name}")
                self.record_activity("trending:edit", guild_id=channel.guild.id)
                return "edited"
        else:
            self.logger.info(
                f"Cannot edit #{channel.name} (missing Manage Channels), announcing instead"
            )

        return await self.announce(config, channel, pulse)

    async def announce(
        self,
        config: TrendingChannelConfig,
        channel: discord.TextChannel,
        pulse: ChannelPulse,
    ) -> str:
        announcement = pulse.announcement.strip()[:ANNOUNCEMENT_MAX]
        perms = channel.permissions_for(channel.guild.me)
        if not announcement or not perms.send_messages:
            self.logger.warning(
                f"Cannot edit or post in #{channel.name}, nothing to do"
            )
            return "skipped"

        message = await channel.send(announcement)
        # our own message must not look like new activity on the next poll
        config.last_seen_message_id = message.id
        self.record_activity("trending:announce", guild_id=channel.guild.id)
        return "announced"


async def setup(bot):
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set, TrendingChannel cannot load")
    await bot.add_cog(TrendingChannel(bot))
