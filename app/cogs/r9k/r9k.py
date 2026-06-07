"""
R9K Cog

Designates a channel as an "R9K mode" channel where every message must be
unique. Duplicate messages (already said in that channel) are deleted, in the
spirit of Randall Munroe's Robot9000 and 4chan's /r9k/.

Matching is per-channel and normalized (lowercased, trimmed, whitespace
collapsed) before hashing, so trivial variations are still caught.
"""

import datetime
import hashlib
import re

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from peewee import IntegrityError
from utils.command_utils import is_bot_owner_or_admin

from .models import R9KConfig, R9KMessage

_WHITESPACE_RE = re.compile(r"\s+")

# Discord caps member timeouts at 28 days.
MAX_TIMEOUT_SECONDS = 28 * 24 * 60 * 60


class R9K(
    LancoCog,
    name="R9K",
    description="R9K channel: every message must be unique, duplicates are removed",
):
    r9k_group = app_commands.Group(name="r9k", description="R9K channel commands")

    def __init__(self, bot):
        super().__init__(bot)

    async def cog_load(self):
        await super().cog_load()
        self.bot.database.create_tables([R9KConfig, R9KMessage])

    @staticmethod
    def normalize(content: str) -> str:
        """Lowercase, trim, and collapse internal whitespace."""
        return _WHITESPACE_RE.sub(" ", content.strip().lower())

    @classmethod
    def hash_content(cls, content: str) -> str:
        normalized = cls.normalize(content)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def is_command(self, message: discord.Message) -> bool:
        """True if the message looks like a bot command and should be ignored."""
        content = message.content

        # This bot's own prefix commands (the prefix alone is not a command).
        guild_prefix = self.bot.get_guild_prefix(message.guild)
        if content.startswith(guild_prefix) and len(content) > len(guild_prefix):
            return True

        # Common prefixes used by other bots in the server.
        known_command_prefixes = ["!", "T!"]  # Default  # Tatsu
        if content.lower().startswith(
            tuple(prefix.lower() for prefix in known_command_prefixes)
        ):
            return True

        return False

    @r9k_group.command(name="set", description="Set the R9K channel for this server")
    @app_commands.describe(channel="The channel to enforce uniqueness in")
    @is_bot_owner_or_admin()
    async def set_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        config, _ = R9KConfig.get_or_create(guild_id=interaction.guild.id)
        config.channel_id = channel.id
        config.enabled = True
        config.save()

        await interaction.response.send_message(
            f"✅ {channel.mention} is now an R9K channel. Every message must be unique!",
            ephemeral=True,
        )

    @r9k_group.command(
        name="disable", description="Disable R9K enforcement for this server"
    )
    @is_bot_owner_or_admin()
    async def disable(self, interaction: discord.Interaction):
        try:
            config = R9KConfig.get(R9KConfig.guild_id == interaction.guild.id)
        except R9KConfig.DoesNotExist:
            await interaction.response.send_message(
                "R9K is not configured for this server.", ephemeral=True
            )
            return

        config.enabled = False
        config.save()
        await interaction.response.send_message(
            "✅ R9K enforcement disabled.", ephemeral=True
        )

    @r9k_group.command(
        name="enable", description="Re-enable R9K enforcement for this server"
    )
    @is_bot_owner_or_admin()
    async def enable(self, interaction: discord.Interaction):
        try:
            config = R9KConfig.get(R9KConfig.guild_id == interaction.guild.id)
        except R9KConfig.DoesNotExist:
            await interaction.response.send_message(
                "R9K is not configured for this server. Use `/r9k set` first.",
                ephemeral=True,
            )
            return

        if not config.channel_id:
            await interaction.response.send_message(
                "No R9K channel is set. Use `/r9k set` first.", ephemeral=True
            )
            return

        config.enabled = True
        config.save()
        await interaction.response.send_message(
            "✅ R9K enforcement enabled.", ephemeral=True
        )

    @r9k_group.command(
        name="timeout",
        description="Set how long to time out a user who posts a duplicate (0 to disable)",
    )
    @app_commands.describe(
        seconds="Timeout duration in seconds (0 disables the timeout; max 28 days)"
    )
    @is_bot_owner_or_admin()
    async def set_timeout(self, interaction: discord.Interaction, seconds: int):
        if seconds < 0:
            await interaction.response.send_message(
                "Timeout must be 0 or greater.", ephemeral=True
            )
            return

        if seconds > MAX_TIMEOUT_SECONDS:
            await interaction.response.send_message(
                f"Timeout cannot exceed 28 days ({MAX_TIMEOUT_SECONDS} seconds).",
                ephemeral=True,
            )
            return

        config, _ = R9KConfig.get_or_create(guild_id=interaction.guild.id)
        config.timeout_seconds = seconds
        config.save()

        if seconds == 0:
            await interaction.response.send_message(
                "✅ Timeout disabled. Duplicate messages will be deleted but users "
                "will not be timed out.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"✅ Users who post a duplicate will now be timed out for "
                f"**{seconds}** second(s).",
                ephemeral=True,
            )

    @r9k_group.command(
        name="ttl",
        description="Set how long a phrase stays 'seen' before it can be reused (0 = forever)",
    )
    @app_commands.describe(
        seconds="History lifetime in seconds (0 means phrases never expire)"
    )
    @is_bot_owner_or_admin()
    async def set_ttl(self, interaction: discord.Interaction, seconds: int):
        if seconds < 0:
            await interaction.response.send_message(
                "TTL must be 0 or greater.", ephemeral=True
            )
            return

        config, _ = R9KConfig.get_or_create(guild_id=interaction.guild.id)
        config.history_ttl_seconds = seconds
        config.save()

        if seconds == 0:
            await interaction.response.send_message(
                "✅ History expiration disabled. Phrases are remembered forever.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"✅ Phrases will now expire after **{seconds}** second(s) and "
                f"can then be reused.",
                ephemeral=True,
            )

    @r9k_group.command(
        name="reset",
        description="Clear the recorded message history for the R9K channel",
    )
    @is_bot_owner_or_admin()
    async def reset(self, interaction: discord.Interaction):
        try:
            config = R9KConfig.get(R9KConfig.guild_id == interaction.guild.id)
        except R9KConfig.DoesNotExist:
            await interaction.response.send_message(
                "R9K is not configured for this server.", ephemeral=True
            )
            return

        if not config.channel_id:
            await interaction.response.send_message(
                "No R9K channel is set.", ephemeral=True
            )
            return

        deleted = (
            R9KMessage.delete()
            .where(R9KMessage.channel_id == config.channel_id)
            .execute()
        )
        await interaction.response.send_message(
            f"✅ Cleared **{deleted}** recorded message(s). The slate is wiped clean.",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return

        try:
            config = R9KConfig.get(R9KConfig.guild_id == message.guild.id)
        except R9KConfig.DoesNotExist:
            return

        if not config.enabled or config.channel_id != message.channel.id:
            return

        # Nothing to dedupe on an empty message (e.g. attachment-only post)
        if not message.content or not self.normalize(message.content):
            return

        # Don't treat bot commands as chat content. Slash commands never reach
        # on_message, but prefix commands do, so skip anything addressed to a bot.
        if self.is_command(message):
            return

        # Drop expired records first so stale phrases can be reused.
        self.purge_expired(message.channel.id, config)

        content_hash = self.hash_content(message.content)

        try:
            R9KMessage.create(
                channel_id=message.channel.id,
                content_hash=content_hash,
                author_id=message.author.id,
                message_id=message.id,
                created_at=datetime.datetime.now(),
            )
        except IntegrityError:
            # Duplicate phrase for this channel, enforce R9K
            await self.handle_duplicate(message, config)

    async def handle_duplicate(self, message: discord.Message, config: R9KConfig):
        try:
            await message.delete()
        except discord.Forbidden:
            self.logger.warning(
                f"Missing permissions to delete duplicate in #{message.channel} "
                f"({message.guild.id})"
            )
            return
        except discord.NotFound:
            return

        timed_out = await self.apply_timeout(message, config)

        notice = (
            f"🤖 Your message in {message.channel.mention} was removed because "
            f"it's already been said there. R9K mode requires every message to be unique."
        )
        if timed_out:
            notice += f"\nYou've been timed out for {config.timeout_seconds} second(s)."

        try:
            await message.author.send(notice)
        except discord.Forbidden:
            pass

    async def apply_timeout(self, message: discord.Message, config: R9KConfig) -> bool:
        """Time out the author if configured. Returns True if a timeout was applied."""
        if config.timeout_seconds <= 0:
            return False

        member = message.author
        if not isinstance(member, discord.Member):
            return False

        duration = datetime.timedelta(seconds=config.timeout_seconds)
        try:
            await member.timeout(duration, reason="R9K: duplicate message")
            return True
        except discord.Forbidden:
            self.logger.warning(
                f"Missing permissions to time out {member} in {message.guild.id}"
            )
        except discord.HTTPException as e:
            self.logger.warning(f"Failed to time out {member}: {e}")
        return False

    def purge_expired(self, channel_id: int, config: R9KConfig) -> int:
        """Delete recorded phrases older than the configured TTL.

        Returns the number of records removed. A TTL of 0 means never expire.
        """
        if config.history_ttl_seconds <= 0:
            return 0

        cutoff = datetime.datetime.now() - datetime.timedelta(
            seconds=config.history_ttl_seconds
        )
        return (
            R9KMessage.delete()
            .where(
                (R9KMessage.channel_id == channel_id) & (R9KMessage.created_at < cutoff)
            )
            .execute()
        )


async def setup(bot):
    await bot.add_cog(R9K(bot))
