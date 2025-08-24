"""
TruthSocial Cog

Description:
TruthSocial embed support
"""

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
        name="truthsocial", description="TruthSocial commands"
    )

    status_pattern = re.compile(
        r"https?://truthsocial\.com/@(?P<handle>[A-Za-z0-9_]+)/posts/(?P<status_id>\d+)"
    )

    user_pattern = re.compile(
        r"https?://truthsocial\.com/@(?P<handle>[A-Za-z0-9_]+)(?:[^\w/].*|/)?$"
    )

    def __init__(self, bot):
        super().__init__(bot)
        self.client = Api(
            username=os.getenv("TRUTH_SOCIAL_USERNAME"),
            password=os.getenv("TRUTH_SOCIAL_PASSWORD"),
        )
        self.bot.database.create_tables([TruthSocialEmbedConfig])
        self.avatar_cache_dir = os.path.join(
            self.get_cog_data_directory(), "AvatarCache"
        )
        self.media_cache_dir = os.path.join(self.get_cog_data_directory(), "MediaCache")
        self.file_downloader = FileDownloader()

    @track_message_ids()
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> discord.Message | None:
        if message.author.bot:
            return

        config = TruthSocialEmbedConfig.get_or_none(guild_id=message.guild.id)
        if not config or not config.enabled:
            return

        status_match = self.status_pattern.search(message.content)
        if status_match:
            handle = status_match.group("handle")
            status_id = status_match.group("status_id")

            status_data = self.client.pull_status(status_id)
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

            avatar_filename = user.avatar_static.split("/")[-1]
            local_avatar_path = os.path.join(self.avatar_cache_dir, avatar_filename)

            files = []

            if not os.path.exists(local_avatar_path):
                self.logger.info(f"Downloading avatar for {user.acct}")
                local_avatar_path = await self.file_downloader.download_file(
                    user.avatar_static, self.avatar_cache_dir, avatar_filename
                )
                self.logger.info(f"Downloaded avatar to {local_avatar_path}")
            avatar_file = discord.File(local_avatar_path, filename=avatar_filename)
            files.append(avatar_file)
            embed.set_thumbnail(url=f"attachment://{avatar_filename}")

            if status.media_attachments and len(status.media_attachments) > 0:
                media_url = status.media_attachments[0].url
                media_filename = media_url.split("/")[-1]
                local_media_path = os.path.join(self.media_cache_dir, media_filename)

                if not os.path.exists(local_media_path):
                    self.logger.info(f"Downloading media for status {status.url}")
                    local_media_path = await self.file_downloader.download_file(
                        media_url, self.media_cache_dir, media_filename
                    )
                    self.logger.info(f"Downloaded media to {local_media_path}")
                media_file = discord.File(local_media_path, filename=media_filename)
                files.append(media_file)
                embed.set_image(url=f"attachment://{media_filename}")

            return await message.channel.send(embed=embed, files=files)

        user_match = self.user_pattern.search(message.content)
        if user_match:
            handle = user_match.group("handle")

            user_data = self.client.lookup(handle)
            user = UserModel(**user_data)

            avatar_filename = user.avatar_static.split("/")[-1]
            local_avatar_path = os.path.join(self.avatar_cache_dir, avatar_filename)

            if not os.path.exists(local_avatar_path):
                self.logger.info(f"Downloading avatar for {user.acct}")
                local_avatar_path = await self.file_downloader.download_file(
                    user.avatar_static, self.avatar_cache_dir, avatar_filename
                )
            file = discord.File(local_avatar_path, filename=avatar_filename)

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
            embed.set_thumbnail(url=f"attachment://{avatar_filename}")
            return await message.channel.send(embed=embed, file=file)

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
