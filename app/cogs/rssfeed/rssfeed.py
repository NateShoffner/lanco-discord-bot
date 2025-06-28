import datetime

import aiohttp
import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands, tasks
from feedparser import parse
from feedparser.util import FeedParserDict
from utils.channel_lock import command_channel_lock
from utils.command_utils import is_bot_owner_or_admin

from .models import RSSFeedConfig


class RssFeed(LancoCog, name="RSSFeed", description="RssFeed cog"):
    UPDATE_INTERVAL = 10  # seconds
    g = app_commands.Group(name="rssfeed", description="RSSFeed commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot.database.create_tables([RSSFeedConfig])

    async def cog_load(self):
        self.poll.start()

    def cog_unload(self):
        self.poll.cancel()

    @g.command(
        name="subscribe",
        description="Subscribe to an RSS feed",
    )
    @is_bot_owner_or_admin()
    async def subscribe(self, interaction: discord.Interaction, url: str):
        embed = discord.Embed(
            title=f"Subscribing to RSS Feed",
            description=f"Checking feed: {url}",
        )

        await interaction.response.send_message(embed=embed)
        response_msg = await interaction.original_response()

        feed = None
        try:
            feed = await self.get_feed(url)
        except Exception as e:
            self.logger.error(e)
            embed.description = "Error checking feed"
            await response_msg.edit(embed=embed)
            return

        config, created = RSSFeedConfig.get_or_create(
            channel_id=interaction.channel.id, url=url
        )

        if not created:
            embed.description = f"Already subscribed to {url}"
            await response_msg.edit(embed=embed)
            return

        self.logger.info(f"Subscribed to {url}")

        title = feed.feed.title

        embed.description = f"Subscribed to {title}\nURL: {url}"
        await response_msg.edit(embed=embed)

    @g.command(
        name="unsubscribe",
        description="Unsubscribe from an RSS feed",
    )
    @is_bot_owner_or_admin()
    async def unsubscribe(self, interaction: discord.Interaction, url: str):
        config = RSSFeedConfig.get_or_none(channel_id=interaction.channel.id, url=url)

        if config:
            config.delete_instance()
            self.logger.info(f"Unsubscribed from {config.url}")

            embed = discord.Embed(
                title=f"Unsubscribed from {config.url}",
            )
            await interaction.response.send_message(embed=embed)

    @tasks.loop(seconds=UPDATE_INTERVAL)
    async def poll(self):
        """Poll for new RSS feed items"""
        for config in RSSFeedConfig.select():
            try:
                self.logger.info(f"Checking feed: {config.url}")
                feed = await self.get_feed(config.url)

                new_items = await self.get_new_items(feed, config.last_checked)

                self.logger.info(f"New items: {len(new_items)}")

                for item in new_items:
                    channel = self.bot.get_channel(config.channel_id)
                    await self.post_item(feed.feed.title, item, channel)

                config.last_checked = datetime.datetime.now()
                config.save()

            except Exception as e:
                self.logger.error(e)

    async def get_feed(self, url: str) -> FeedParserDict:
        """Get the feed"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                text = await response.text()
                parsed = parse(text)
                return parsed

    async def is_new_item(self, entry: str, last_checked: datetime.datetime) -> bool:
        """Check if an item is new"""
        published = entry.published_parsed or entry.updated_parsed
        if not published:
            return False
        if not last_checked:
            return True
        return datetime.datetime(*published[:6]) > last_checked

    async def get_new_items(
        self, feed: FeedParserDict, last_checked: datetime.datetime
    ) -> list[FeedParserDict]:
        """Get new items from the feed"""
        return [
            entry
            for entry in feed.entries
            if await self.is_new_item(entry, last_checked)
        ]

    async def post_item(
        self, source_name: str, item: FeedParserDict, channel: discord.TextChannel
    ):
        """Post an item to the channel"""
        embed = discord.Embed(
            title=item.title,
            url=item.link,
            description=item.description,
            timestamp=datetime.datetime(*item.published_parsed[:6]),
        )
        embed.set_author(name=source_name)
        await channel.send(embed=embed)

    @commands.command(name="rsstest", description="Test the Reddit feed")
    @is_bot_owner_or_admin()
    async def test(self, ctx: commands.Context):
        feed = await self.get_feed("https://www.cityoflancasterpa.gov/feed/")
        yesterday = datetime.datetime.now() - datetime.timedelta(days=3)
        new_items = await self.get_new_items(feed, yesterday)
        first_item = new_items[0]

        await self.post_item(feed.feed.title, first_item, ctx.channel)


async def setup(bot):
    await bot.add_cog(RssFeed(bot))
