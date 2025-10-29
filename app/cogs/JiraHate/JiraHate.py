"""
JiraHate Cog

Description:
Random IFuckingHateJira quotes
"""

import random

import aiohttp
import discord
from bs4 import BeautifulSoup
from cogs.lancocog import LancoCog
from discord.ext import commands, tasks
from feedparser import parse
from pydantic import BaseModel
from utils.markdown_utils import html_to_markdown

BASE_URL = "https://ifuckinghatejira.com/"


class JiraQuote(BaseModel):
    id: int
    quote: str
    url: str


class FeedItem(BaseModel):
    title: str
    link: str
    description: str
    pubDate: str


class JiraHate(
    LancoCog,
    name="JiraHate",
    description="Random IFuckingHateJira quotes.",
):
    UPDATE_INTERVAL = 300  # seconds

    def __init__(self, bot):
        super().__init__(bot)
        self.quotes = dict[int, JiraQuote]()
        self.latest_quote_id = None

    async def cog_load(self):
        self.get_feed.start()

    def cog_unload(self):
        self.get_feed.cancel()

    @tasks.loop(seconds=UPDATE_INTERVAL)
    async def get_feed(self) -> list[FeedItem]:
        """Fetch the latest quotes from IFuckingHateJira"""
        feed_items = []
        url = f"{BASE_URL}feed.xml"
        self.logger.info(f"Fetching feed from {url}")
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                feed_text = await response.text()
                feed = parse(feed_text)
                items = feed.entries

                for item in items:
                    feed_item = FeedItem(
                        title=item.title,
                        link=item.link,
                        description=item.description,
                        pubDate=item.published,
                    )

                self.latest_quote_id = self.get_latest_id(items)
                return feed_items

    async def get_quote_by_id(self, quote_id: int) -> JiraQuote:
        """Get a quote by its ID"""
        if quote_id in self.quotes:
            return self.quotes[quote_id]

        url = f"{BASE_URL}{quote_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                page_content = await response.text()
                soup = BeautifulSoup(page_content, "html.parser")
                quote_text = soup.select_one("blockquote").decode_contents()
                quote = JiraQuote(
                    id=quote_id,
                    quote=html_to_markdown(quote_text),
                    url=url,
                )

                # TODO <em>

                self.quotes[quote_id] = quote
                return quote

    def get_latest_id(self, items: list[FeedItem]) -> int:
        """Get the latest quote ID"""
        latest_id = None
        for item in items:
            if not item.title.isdigit():
                continue

            tint = int(item.title)

            if not latest_id or tint > latest_id:
                latest_id = tint
        return latest_id

    @commands.command()
    async def jira(self, ctx):
        """Responds with a random IFuckingHateJira quote."""

        if not self.latest_quote_id:
            self.logger.error("No quotes available yet.")
            return

        random_id = random.randint(1, self.latest_quote_id)
        quote = await self.get_quote_by_id(random_id)

        embed = discord.Embed(
            title="I fucking hate Jira.",
            description=quote.quote,
            color=discord.Color.blue(),
            url=quote.url,
        )

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(JiraHate(bot))
