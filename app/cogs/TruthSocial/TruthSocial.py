"""
TruthSocial Cog

Description:
TruthSocial embed support
"""

import asyncio
import os
import re

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from truthbrush.api import Api
from utils.command_utils import is_bot_owner_or_admin
from utils.file_downloader import FileDownloader
from utils.tracked_message import track_message_ids

from .models import StatusModel, TruthSocialEmbedConfig, UserModel

EMBED_ICON_URL = "https://truthsocial.com/favicon.png"


class TruthSocial(
    LancoCog,
    name="TruthSocial",
    description="TruthSocial embed support",
):
    truth_social_group = app_commands.Group(
        name="truthsocial", description="TruthSocial commands", guild_only=True
    )

    status_pattern = re.compile(
        r"https?://truthsocial\.com/@(?P<handle>[A-Za-z0-9_]+)/posts/(?P<status_id>\d+)"
    )

    user_pattern = re.compile(
        r"https?://truthsocial\.com/@(?P<handle>[A-Za-z0-9_]+)(?:[^\w/].*|/)?$"
    )

    def __init__(self, bot):
        super().__init__(bot)
        self.client = None
        self.avatar_cache_dir = os.path.join(
            self.get_cog_data_directory(), "AvatarCache"
        )
        self.media_cache_dir = os.path.join(self.get_cog_data_directory(), "MediaCache")
        self.file_downloader = FileDownloader()

    async def cog_load(self):
        await super().cog_load()
        self.bot.database.create_tables([TruthSocialEmbedConfig])

        username = os.getenv("TRUTH_SOCIAL_USERNAME")
        password = os.getenv("TRUTH_SOCIAL_PASSWORD")
        token = os.getenv("TRUTH_SOCIAL_TOKEN")

        # truthbrush builds its Api lazily and only validates credentials on the
        # first call, so without this check a missing username surfaces as a
        # LoginErrorException out of on_message rather than at load.
        if not token and not (username and password):
            self.logger.warning(
                "TruthSocial cog is missing TRUTH_SOCIAL_TOKEN or "
                "TRUTH_SOCIAL_USERNAME/TRUTH_SOCIAL_PASSWORD, embeds will be disabled"
            )
            return

        self.logger.info(
            f"TruthSocial credentials loaded ({'token' if token else 'username'})"
        )
        self.client = Api(username=username, password=password, token=token)

    async def fetch(self, func, *args):
        """Run a blocking truthbrush call off the event loop.

        Returns None if the call fails. truthbrush raises on auth trouble and
        on any non-200, and an exception escaping a listener takes out the
        whole on_message dispatch for that message.
        """
        try:
            return await asyncio.to_thread(func, *args)
        except Exception:
            self.logger.error(
                f"TruthSocial API call {func.__name__} failed", exc_info=True
            )
            return None

    async def get_cached_file(self, url: str, cache_dir: str) -> str | None:
        """Return a local path for url, downloading it on first use.

        None when the file cannot be fetched. download_file returns None on any
        non-200, which discord.File would then choke on, so callers drop the
        attachment and send the embed without it rather than lose the embed.
        """
        filename = url.split("/")[-1].split("?")[0]
        local_path = os.path.join(cache_dir, filename)

        if os.path.exists(local_path):
            return local_path

        try:
            self.logger.info(f"Downloading {url}")
            return await self.file_downloader.download_file(url, cache_dir, filename)
        except Exception:
            self.logger.error(f"Failed to download {url}", exc_info=True)
            return None

    @track_message_ids()
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> discord.Message | None:
        if message.author.bot or message.guild is None:
            return

        config = TruthSocialEmbedConfig.get_or_none(guild_id=message.guild.id)
        if not config or not config.enabled:
            return

        if self.client is None:
            return

        status_match = self.status_pattern.search(message.content)
        if status_match:
            handle = status_match.group("handle")
            status_id = status_match.group("status_id")

            status_data = await self.fetch(self.client.pull_status, status_id)
            if not status_data:
                return
            status = StatusModel(**status_data)

            user = status.account

            desc = status.markdown_content()

            desc += (
                f"\n\n💬 {status.replies_count:,} • "
                f"🔁 {status.reblogs_count:,} • "
                f"❤️ {status.favourites_count:,}"
            )

            embed = discord.Embed(
                title=f"{user.display_name} (@{user.acct})",
                url=status.url,
                description=desc,
                color=discord.Color.blue(),
            )
            embed.timestamp = status.created_at

            files = []

            avatar_path = await self.get_cached_file(
                user.avatar_static, self.avatar_cache_dir
            )
            if avatar_path:
                avatar_filename = os.path.basename(avatar_path)
                files.append(discord.File(avatar_path, filename=avatar_filename))
                embed.set_thumbnail(url=f"attachment://{avatar_filename}")

            if status.media_attachments:
                media_path = await self.get_cached_file(
                    status.media_attachments[0].url, self.media_cache_dir
                )
                if media_path:
                    media_filename = os.path.basename(media_path)
                    files.append(discord.File(media_path, filename=media_filename))
                    embed.set_image(url=f"attachment://{media_filename}")

            return await message.channel.send(embed=embed, files=files)

        user_match = self.user_pattern.search(message.content)
        if user_match:
            handle = user_match.group("handle")

            user_data = await self.fetch(self.client.lookup, handle)
            if not user_data:
                return
            user = UserModel(**user_data)

            desc = user.markdown_note()

            desc += (
                f"\n\n👥 {user.followers_count:,} followers • "
                f"👤 {user.following_count:,} following • "
                f"📝 {user.statuses_count:,} posts"
            )

            embed = discord.Embed(
                title=f"{user.display_name} (@{user.acct})",
                url=user.url,
                description=desc,
                color=discord.Color.blue(),
            )

            avatar_path = await self.get_cached_file(
                user.avatar_static, self.avatar_cache_dir
            )
            if not avatar_path:
                return await message.channel.send(embed=embed)

            avatar_filename = os.path.basename(avatar_path)
            embed.set_thumbnail(url=f"attachment://{avatar_filename}")
            return await message.channel.send(
                embed=embed,
                file=discord.File(avatar_path, filename=avatar_filename),
            )

    @truth_social_group.command(
        name="toggle", description="Enable or disable TruthSocial embeds"
    )
    @is_bot_owner_or_admin()
    async def toggle(self, interaction: discord.Interaction):
        """Enable or disable TruthSocial embeds in this server"""
        config, created = TruthSocialEmbedConfig.get_or_create(
            guild_id=interaction.guild.id
        )
        if created or not config.enabled:
            config.enabled = True
            config.save()
            await interaction.response.send_message(
                f"TruthSocial embeds enabled for this server"
            )
        else:
            config.enabled = False
            config.save()
            await interaction.response.send_message(
                f"TruthSocial embeds disabled for this server"
            )


async def setup(bot):
    await bot.add_cog(TruthSocial(bot))
