"""
RandomNsfwSubreddit Cog

Description:
RandomNsfwSubreddit cog
"""

import os
import random
import re

import aiohttp
import asyncpraw
import cachetools
import discord
from asyncpraw.models import Subreddit
from cogs.lancocog import LancoCog
from discord.ext import commands


class RandomNsfwReddit(
    LancoCog,
    name="RandomNsfwReddit",
    description="RandomNsfwReddit cog",
):
    def __init__(self, bot):
        super().__init__(bot)
        self.reddit = asyncpraw.Reddit(
            client_id=os.getenv("REDDIT_ID"),
            client_secret=os.getenv("REDDIT_SECRET"),
            user_agent="LanCo Discord Bot (by /u/syntack)",
        )
        self.nsfw_subreddits_cache = cachetools.TTLCache(
            maxsize=100, ttl=60 * 60 * 12
        )  # 12 hours

    async def fetch_subreddits_from_nsfw411(self) -> list[str]:
        if "nsfw_subreddits" in self.nsfw_subreddits_cache:
            return self.nsfw_subreddits_cache["nsfw_subreddits"]

        self.logger.debug("Fetching NSFW411 subreddits...")

        url = "https://www.reddit.com/r/NSFW411/wiki/index/.json"
        headers = {"User-Agent": "DiscordBot/1.0"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                content = data["data"]["content_md"]

        # Extract subreddit names
        matches = re.findall(r"r/([A-Za-z0-9_]+)", content)
        unique_subs = list(set(matches))
        self.logger.debug(f"Fetched {len(unique_subs)} NSFW subreddits.")

        # Cache the result
        self.nsfw_subreddits_cache["nsfw_subreddits"] = unique_subs

        return unique_subs

    async def get_random_nsfw_subreddit(self) -> Subreddit:
        candidates = await self.fetch_subreddits_from_nsfw411()
        random.shuffle(candidates)
        for name in candidates:
            try:
                sub = await self.reddit.subreddit(name, fetch=True)
                if sub.over18:
                    return sub
            except:
                continue
        return None

    @commands.command(name="randomnsfw")
    @commands.is_nsfw()
    async def random_nsfw(self, ctx):
        sub = await self.get_random_nsfw_subreddit()
        if not sub:
            return await ctx.send("Couldn't find a valid NSFW subreddit from NSFW411.")

        url = f"https://reddit.com/r/{sub.display_name}"

        embed = discord.Embed(
            title=f"r/{sub.display_name}",
            url=url,
            description=sub.public_description or "No description available.",
            color=discord.Color.red(),
        )

        if sub.icon_img:
            embed.set_thumbnail(url=sub.icon_img)

        await ctx.send(embed=embed)

    @commands.command(name="randomnsfwcount")
    @commands.is_nsfw()
    async def random_nsfw_count(self, ctx):
        """Show the number of NSFW subreddits in the cache"""
        count = len(self.nsfw_subreddits_cache.get("nsfw_subreddits", []))
        await ctx.send(f"Number of NSFW subreddits in cache: {count}")


async def setup(bot):
    await bot.add_cog(RandomNsfwReddit(bot))
