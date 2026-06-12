import datetime
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import aiohttp
import discord
from aiogoogle import Aiogoogle
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands, tasks
from utils.command_utils import is_bot_owner_or_admin

from .models import YoutubeSubscription


@dataclass
class YoutubeVideo:
    channel_name: str
    video_id: str
    uploaded_at: str


class Youtube(
    LancoCog,
    name="Youtube",
    description="Subscribe to YouTube channels and post new video notifications",
):
    g = app_commands.Group(name="youtube", description="Youtube commands")

    UPDATE_INTERVAL = 10 * 60  # 10 minutes

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.google = Aiogoogle(api_key=os.getenv("YOUTUBE_API_KEY"))
        self.bot.database.create_tables([YoutubeSubscription])

    async def cog_load(self):
        self.poll.start()

    def cog_unload(self):
        self.poll.cancel()

    @tasks.loop(seconds=UPDATE_INTERVAL)
    async def poll(self):
        """Poll for new videos from subscribed channels"""
        self.logger.info("Polling...")
        try:
            await self.get_new_videos()
        except Exception as e:
            self.logger.error(f"Error polling: {e}")

    async def get_new_videos(self):
        """Get new videos from watched channels and share them to the configured channels"""
        youtube_configs = YoutubeSubscription.select()
        if not youtube_configs:
            return

        # build up a map of channels and configs to post to for efficiency
        youtube_channels = {}
        for youtube_config in youtube_configs:
            if not youtube_config.yt_channel_id in youtube_channels:
                youtube_channels[youtube_config.yt_channel_id] = []
            youtube_channels[youtube_config.yt_channel_id].append(youtube_config)

        for channel, configs in youtube_channels.items():
            self.logger.info(f"Checking for new videos from channel: {channel}")

            videos = await self.get_latest_videos(channel, limit=5)
            videos.sort(key=lambda x: x.uploaded_at, reverse=True)

            for video in videos:
                for config in configs:
                    published = video.uploaded_at

                    # skip old videos
                    if config.last_publish and published <= config.last_publish:
                        continue

                    url = "https://www.youtube.com/watch?v=" + video.video_id
                    self.logger.info(
                        f"Found new video in {channel} for {config.channel_id}: {url}"
                    )

                    channel = self.bot.get_channel(config.channel_id)
                    if not channel:
                        self.logger.error(
                            f"Channel {config.channel_id} not found, skipping"
                        )
                        continue

                    msg = await self.share_video(video, channel)
                    config.last_publish = published
                    config.save()

    async def share_video(self, video: YoutubeVideo, channel: discord.TextChannel):
        url = f"https://www.youtube.com/watch?v={video.video_id}"
        msg = f"**New video from {video.channel_name}**: {url}"
        await channel.send(msg)

    @g.command(name="subscribe", description="Subscribe to a Youtube channel")
    @is_bot_owner_or_admin()
    async def subscribe(self, interaction: discord.Interaction, channel_id: str):
        id = await self.get_channel_id(channel_id)

        if id is None:
            await interaction.response.send_message(
                f"Channel not found with id: {channel_id}"
            )
            return

        youtube_config, createad = YoutubeSubscription.get_or_create(
            channel_id=interaction.channel_id,
            guild_id=interaction.guild_id,
            yt_channel_id=id,
        )
        youtube_config.last_publish = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
        youtube_config.save()

        await interaction.response.send_message(f"Subscribed to channel <{channel_id}>")

    @g.command(name="unsubscribe", description="Unsubscribe from a Youtube channel")
    @is_bot_owner_or_admin()
    async def unsubscribe(self, interaction: discord.Interaction, channel_id: str):
        id = await self.get_channel_id(channel_id)

        if id is None:
            await interaction.response.send_message(
                f"Channel not found with id: {channel_id}"
            )
            return

        youtube_config = YoutubeSubscription.get_or_none(
            channel_id=interaction.channel.id,
            guild_id=interaction.guild_id,
            yt_channel_id=id,
        )

        if not youtube_config:
            embed = discord.Embed(
                title=f"Not subscribed to {channel_id}",
                color=discord.Color(0xFF0000),
            )
            await interaction.response.send_message(embed=embed)
            return
        youtube_config.delete_instance()

        embed = discord.Embed(
            title=f"Unsubscribe from {channel_id}",
            color=discord.Color(0x00FF00),
        )

        await interaction.response.send_message(embed=embed)

    async def get_channel_id(self, username_or_custom_url: str) -> YoutubeVideo:
        # remove everything before the last / in the URL
        username_or_custom_url = username_or_custom_url.split("/")[-1]
        # also remove the @
        username_or_custom_url = username_or_custom_url.lstrip("@")

        youtube_api = await self.google.discover("youtube", "v3")
        response = await self.google.as_api_key(
            youtube_api.channels.list(part="id", forHandle=username_or_custom_url)
        )
        if "items" in response and len(response["items"]) > 0:
            channel_id = response["items"][0]["id"]
            return channel_id
        else:
            return None

    async def get_latest_videos(
        self, channel_id: str, limit: int = 1
    ) -> list[YoutubeVideo]:
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(feed_url) as response:
                if response.status != 200:
                    self.logger.error(
                        f"RSS feed returned {response.status} for channel {channel_id}"
                    )
                    return []
                text = await response.text()

        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "yt": "http://www.youtube.com/xml/schemas/2015",
        }
        root = ET.fromstring(text)

        videos = []
        for entry in root.findall("atom:entry", ns)[:limit]:
            video_id = entry.find("yt:videoId", ns).text
            channel_name = entry.find("atom:author/atom:name", ns).text
            uploaded_at = entry.find("atom:published", ns).text
            videos.append(YoutubeVideo(channel_name, video_id, uploaded_at))

        return videos


async def setup(bot):
    await bot.add_cog(Youtube(bot))
