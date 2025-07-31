"""
RandomNsfwSubreddit Cog

Description:
RandomNsfwSubreddit cog
"""

import asyncio
import os
import random
import re

import aiohttp
import asyncpraw
import discord
from asyncpraw.models import Subreddit
from cogs.lancocog import LancoCog
from discord.ext import commands, tasks


class RandomNsfwReddit(
    LancoCog,
    name="RandomNsfwReddit",
    description="RandomNsfwReddit cog",
):
    UPDATE_INTERVAL = 6 * 60 * 60  # 6 hours in seconds

    def __init__(self, bot):
        super().__init__(bot)
        self.reddit = asyncpraw.Reddit(
            client_id=os.getenv("REDDIT_ID"),
            client_secret=os.getenv("REDDIT_SECRET"),
            user_agent="LanCo Discord Bot (by /u/syntack)",
        )
        self.nsfw_subreddits_cache = []
        self.last_updated = None

    async def cog_load(self):
        self.update_nsfw_subreddits.start()

    def cog_unload(self):
        self.update_nsfw_subreddits.cancel()

    @tasks.loop(seconds=UPDATE_INTERVAL)
    async def update_nsfw_subreddits(self):
        """Periodically update the NSFW subreddits cache."""
        self.logger.info("Updating NSFW subreddits cache...")
        try:
            await self.fetch_subreddits_from_nsfw411()
            self.logger.info("NSFW subreddits cache updated successfully.")
        except Exception as e:
            self.logger.error(f"Failed to update NSFW subreddits: {e}")

    async def fetch_subreddits_from_nsfw411(self) -> list[str]:
        self.logger.debug("Fetching NSFW411 subreddits...")

        def get_full_list_url(page_num: int) -> str:
            return f"https://www.reddit.com/r/NSFW411/wiki/fulllist{page_num}.json"

        headers = {"User-Agent": "DiscordBot/1.0"}
        total_pages = 9  # TODO infer from the wiki page

        # if the cache is empty, we can safely just update the existing cache
        update_live_cache = len(self.nsfw_subreddits_cache) == 0
        new_cache = []

        for page in range(1, total_pages + 1):
            url = get_full_list_url(page)
            self.logger.debug(f"Fetching page {page} from NSFW411: {url}")

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        self.logger.error(
                            f"Failed to fetch page {page}: {resp.status} - {url}"
                        )
                        continue
                    data = await resp.json()
                    content = data["data"]["content_md"]

                    unique_subs = set()  # to avoid duplicates

                    # Extract subreddit names
                    matches = re.findall(r"r/([A-Za-z0-9_]+)", content)
                    for match in matches:
                        if match not in unique_subs:
                            unique_subs.add(match)

                    self.logger.info(
                        f"Fetched {len(unique_subs)} subreddits from page {page}."
                    )
                    if update_live_cache:
                        self.nsfw_subreddits_cache.extend(unique_subs)
                        self.last_updated = discord.utils.utcnow()
                    else:
                        new_cache.extend(unique_subs)
                    await asyncio.sleep(0.25)  # rate limit

        if not update_live_cache:
            self.nsfw_subreddits_cache = new_cache

        self.logger.debug(
            f"Fetched a total of {len(unique_subs)} NSFW subreddits from all pages."
        )

        self.last_updated = discord.utils.utcnow()

    async def get_random_nsfw_subreddit(self) -> Subreddit:
        """Get a random NSFW subreddit from the cached list."""
        candidates = self.nsfw_subreddits_cache
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
        count = len(self.nsfw_subreddits_cache)
        embed = discord.Embed(
            title="NSFW Subreddit Cache Count",
            color=discord.Color.red(),
        )
        embed.add_field(
            name="Total",
            value=f"{count:,}",
            inline=False,
        )
        if self.last_updated:
            rel_time = discord.utils.format_dt(self.last_updated, style="R")
            updated_text = f"Last updated: {rel_time}"
        else:
            updated_text = "Last updated: Never"
        embed.add_field(
            name="Last Updated",
            value=updated_text,
            inline=False,
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(RandomNsfwReddit(bot))
