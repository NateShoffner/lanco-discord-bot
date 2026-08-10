import datetime
from urllib.parse import urlparse

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


class RssFeed(
    LancoCog,
    name="RSSFeed",
    description="Poll RSS feeds and post new entries to configured channels",
):
    UPDATE_INTERVAL = 10  # seconds
    g = app_commands.Group(name="rssfeed", description="RSSFeed commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot.database.create_tables([RSSFeedConfig])
        self._warned_channels: set[int] = set()
        # feed urls already warned about, so a persistently broken feed does not
        # emit a warning on every poll
        self._warned_feeds: set[str] = set()

    async def cog_load(self):
        self.poll.start()

    def cog_unload(self):
        self.poll.cancel()

    @staticmethod
    def feed_label(url: str) -> str:
        """Short host-based label used to prefix log lines"""
        host = urlparse(url).netloc
        if host.startswith("www."):
            host = host[4:]
        return host or url

    def warn_once(self, url: str, message: str) -> None:
        """Warn about a feed only the first time, since polling is frequent"""
        if url not in self._warned_feeds:
            self._warned_feeds.add(url)
            self.logger.warning(message)

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

        label = self.feed_label(url)

        feed = None
        try:
            feed = await self.get_feed(url)
        except Exception:
            self.logger.exception(
                f"[{label}] {interaction.user} failed to subscribe channel "
                f"{interaction.channel.id} to {url}"
            )
            embed.description = "Error checking feed"
            await response_msg.edit(embed=embed)
            return

        config, created = RSSFeedConfig.get_or_create(
            channel_id=interaction.channel.id, url=url
        )

        if not created:
            self.logger.info(
                f"[{label}] Channel {interaction.channel.id} is already "
                f"subscribed to {url}"
            )
            embed.description = f"Already subscribed to {url}"
            await response_msg.edit(embed=embed)
            return

        self.logger.info(
            f"[{label}] {interaction.user} subscribed channel "
            f"{interaction.channel.id} to {url} ({len(feed.entries)} item(s) "
            f"currently in feed)"
        )

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
            self._warned_feeds.discard(config.url)
            self.logger.info(
                f"[{self.feed_label(config.url)}] {interaction.user} unsubscribed "
                f"channel {interaction.channel.id} from {config.url}"
            )

            embed = discord.Embed(
                title=f"Unsubscribed from {config.url}",
            )
            await interaction.response.send_message(embed=embed)
        else:
            self.logger.info(
                f"[{self.feed_label(url)}] {interaction.user} tried to unsubscribe "
                f"channel {interaction.channel.id} from {url}, no matching "
                f"subscription"
            )

    @tasks.loop(seconds=UPDATE_INTERVAL)
    async def poll(self):
        """Poll for new RSS feed items"""
        configs = list(RSSFeedConfig.select())
        if not configs:
            return

        self.logger.debug(f"Polling {len(configs)} feed subscription(s)")

        for config in configs:
            label = self.feed_label(config.url)
            try:
                self.logger.debug(f"[{label}] Checking {config.url}")
                feed = await self.get_feed(config.url)

                if not feed.entries:
                    reason = getattr(feed, "bozo_exception", None)
                    self.warn_once(
                        config.url,
                        f"[{label}] Feed returned no entries"
                        + (f": {reason}" if reason else ""),
                    )
                elif feed.bozo:
                    # parsed well enough to yield entries, so note it and carry on
                    self.warn_once(
                        config.url,
                        f"[{label}] Feed is malformed but yielded "
                        f"{len(feed.entries)} entries: "
                        f"{getattr(feed, 'bozo_exception', 'unknown error')}",
                    )
                else:
                    self._warned_feeds.discard(config.url)

                new_items = await self.get_new_items(feed, config.last_checked)

                if config.last_checked is None:
                    # everything in the feed counts as new on the very first poll
                    self.logger.info(
                        f"[{label}] First poll since subscribing, "
                        f"{len(new_items)} of {len(feed.entries)} item(s) treated as new"
                    )
                elif new_items:
                    self.logger.info(
                        f"[{label}] {len(new_items)} new item(s) of "
                        f"{len(feed.entries)} in feed"
                    )

                channel = self.bot.get_channel(config.channel_id)
                if new_items and not channel:
                    if config.channel_id not in self._warned_channels:
                        self._warned_channels.add(config.channel_id)
                        self.logger.warning(
                            f"[{label}] Channel {config.channel_id} not found, "
                            f"skipping {len(new_items)} item(s)"
                        )

                for item in new_items:
                    if not channel:
                        continue
                    msg = await self.post_item(feed.feed.title, item, channel)
                    self.logger.info(
                        f"[{label}] Posted {getattr(item, 'link', '?')} "
                        f"to channel {config.channel_id} as message {msg.id}"
                    )

                # feedparser normalises entry timestamps to UTC, so the watermark
                # must be UTC too. Using local time here made every item published
                # within the UTC offset compare as new on every poll, re-posting
                # it until it aged out of the feed.
                config.last_checked = datetime.datetime.utcnow()
                config.save()

            except Exception:
                self.logger.exception(
                    f"[{label}] Error polling {config.url} for channel "
                    f"{config.channel_id}"
                )

    async def get_feed(self, url: str) -> FeedParserDict:
        """Get the feed"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    self.warn_once(
                        url,
                        f"[{self.feed_label(url)}] HTTP {response.status} fetching {url}",
                    )
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
    ) -> discord.Message:
        """Post an item to the channel"""
        embed = discord.Embed(
            title=item.title,
            url=item.link,
            description=item.description,
            timestamp=datetime.datetime(
                *item.published_parsed[:6], tzinfo=datetime.timezone.utc
            ),
        )
        embed.set_author(name=source_name)
        return await channel.send(embed=embed)

    @commands.command(name="rsstest", description="Test the Reddit feed")
    @is_bot_owner_or_admin()
    async def test(self, ctx: commands.Context):
        feed = await self.get_feed("https://www.cityoflancasterpa.gov/feed/")
        yesterday = datetime.datetime.utcnow() - datetime.timedelta(days=3)
        new_items = await self.get_new_items(feed, yesterday)
        first_item = new_items[0]

        await self.post_item(feed.feed.title, first_item, ctx.channel)


async def setup(bot):
    await bot.add_cog(RssFeed(bot))
