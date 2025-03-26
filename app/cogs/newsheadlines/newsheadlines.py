import asyncio
import os
from datetime import datetime
from typing import Optional

import aiohttp
import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from pydantic import BaseModel
from utils.channel_lock import command_channel_lock


class Headline(BaseModel):
    title: str
    description: Optional[str]
    url: str
    source: str
    published_at: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class NewsHeadlines(LancoCog, name="NewsHeadlines", description="NewsHeadlines cog"):
    MAX_HEADLINES = 5
    BASE_URL = "https://newsapi.org/v2"

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    @commands.command(name="trump", description="Get the latest news about Trump")
    @command_channel_lock()
    async def trump(self, ctx: commands.Context):
        await ctx.channel.typing()
        headlines = await self.get_top_headlines("trump")
        embed = await self.create_embed(
            headlines, "Latest news about Trump", discord.Color.orange()
        )
        await ctx.send(embed=embed)

    async def create_embed(
        self, headlines: list[Headline], title: str, color: discord.Color
    ) -> discord.Embed:
        embed = discord.Embed(title=title, color=color)
        desc = ""

        for headline in headlines[: self.MAX_HEADLINES]:
            desc += f"[{headline.title}]({headline.url}) - ({headline.published_at.strftime('%b %d %H:%M')})\n"

        embed.description = desc
        return embed

    async def fetch_news(self, endpoint, params=None):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/{endpoint}",
                params={**params, "apiKey": os.getenv("NEWSAPI_API_KEY")},
            ) as response:
                return await response.json()

    async def get_top_headlines(self, query: str) -> list[Headline]:
        params = {"q": query, "country": "us"}
        articles = await self.fetch_news("top-headlines", params)

        headlines = []

        for article in articles["articles"]:
            headline = Headline(
                title=article["title"],
                description=article.get("description"),
                url=article["url"],
                source=article["source"]["name"],
                published_at=article.get("publishedAt"),
            )
            headlines.append(headline)

        # sort the headlines by published date
        headlines.sort(key=lambda x: x.published_at, reverse=True)
        return headlines


async def setup(bot):
    await bot.add_cog(NewsHeadlines(bot))
