"""
TruthSocial Cog

Description:
TruthSocial embed support
"""

import os
import re
from datetime import datetime
from typing import Any, Optional

import discord
from cogs.lancocog import LancoCog
from discord.ext import commands
from pydantic import BaseModel
from truthbrush.api import Api
from utils.file_downloader import FileDownloader
from utils.markdown_utils import html_to_markdown
from utils.tracked_message import track_message_ids


class UserModel(BaseModel):
    id: str
    username: str
    acct: str
    display_name: str
    locked: bool
    bot: bool
    group: bool
    created_at: datetime
    note: str
    url: str
    avatar: str
    avatar_static: str
    header: str
    header_static: str
    followers_count: int
    following_count: int
    statuses_count: int
    last_status_at: str
    verified: bool
    location: str
    website: str

    # note needs to be converted from HTML to markdown
    def markdown_note(self):
        return html_to_markdown(self.note)


class MetaData(BaseModel):
    aspect: float
    height: int
    size: str
    width: int


class Meta(BaseModel):
    original: MetaData
    small: MetaData


class MediaAttachment(BaseModel):
    id: str
    type: str
    url: str
    preview_url: str
    external_video_id: Any
    remote_url: Any
    preview_remote_url: Any
    text_url: Any
    meta: Meta
    description: Optional[str]
    blurhash: str
    processing: str


class StatusModel(BaseModel):
    id: str
    created_at: datetime
    sensitive: bool
    spoiler_text: str
    visibility: str
    uri: str
    url: str
    content: str
    account: UserModel
    media_attachments: list[MediaAttachment]
    sponsored: bool
    replies_count: int
    reblogs_count: int
    favourites_count: int
    upvotes_count: int
    downvotes_count: int
    favourited: bool
    reblogged: bool
    muted: bool
    pinned: bool
    bookmarked: bool
    votable: bool
    edited_at: Any
    version: str
    editable: bool

    def markdown_content(self):
        return html_to_markdown(self.content)


EMBED_ICON_URL = "https://truthsocial.com/favicon.png"


class TruthSocial(
    LancoCog,
    name="TruthSocial",
    description="TruthSocial cog",
):

    # https://truthsocial.com/@realDonaldTrump/posts/114279756371714617
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


async def setup(bot):
    await bot.add_cog(TruthSocial(bot))
