import datetime
import os

import asyncpraw
import cachetools
import discord
from asyncpraw.models import Submission
from cogs.lancocog import LancoCog
from discord import TextChannel, app_commands
from discord.ext import commands, tasks
from utils.command_utils import is_bot_owner_or_admin

from .models import RedditFeedConfig, RedditPost


class RedditFeed(LancoCog):
    reddit_feed_group = app_commands.Group(
        name="reddit", description="Poll Reddit for new posts"
    )

    UPDATE_INTERVAL = 10  # seconds
    POST_LIMIT = 5  # TODO: make this configurable

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot.database.create_tables([RedditFeedConfig, RedditPost])
        self.reddit = asyncpraw.Reddit(
            client_id=os.getenv("REDDIT_ID"),
            client_secret=os.getenv("REDDIT_SECRET"),
            user_agent="LanCo Discord Bot (by /u/syntack)",
        )
        self.subreddit_icon_cache = cachetools.TTLCache(
            maxsize=100, ttl=60 * 60 * 24
        )  # 24 hours

    async def cog_load(self):
        self.poll.start()

    def cog_unload(self):
        self.poll.cancel()

    @tasks.loop(seconds=UPDATE_INTERVAL)
    async def poll(self):
        """Poll for new posts in watched subreddits"""
        self.logger.info("Polling...")
        try:
            await self.get_new_posts()
        except Exception as e:
            self.logger.error(f"Error polling: {e}")

    async def get_new_posts(self):
        """Get new posts from watched subreddits and share them to the configured channels"""
        reddit_configs = RedditFeedConfig.select()
        if not reddit_configs:
            return

        # build up a map of subreddits and configs to post to for efficiency
        subreddit_channels = {}
        for reddit_config in reddit_configs:
            if not reddit_config.subreddit in subreddit_channels:
                subreddit_channels[reddit_config.subreddit] = []
            subreddit_channels[reddit_config.subreddit].append(reddit_config)

        for sr, configs in subreddit_channels.items():
            self.logger.info(f"Checking for new posts in /r/{sr}")
            subreddit = await self.reddit.subreddit(sr)

            submissions = []
            async for submission in subreddit.new(limit=self.POST_LIMIT):
                submissions.append(submission)
            submissions = sorted(submissions, key=lambda s: s.created_utc)

            for submission in submissions:
                for config in configs:
                    created = submission.created_utc

                    # skip posts we've already seen
                    if (
                        config.last_known_post_creation
                        and created <= config.last_known_post_creation
                    ):
                        continue

                    permalink = f"https://reddit.com{submission.permalink}"
                    self.logger.info(
                        f"Found new post in {sr} for {config.channel_id}: {permalink}"
                    )

                    channel = self.bot.get_channel(config.channel_id)
                    if not channel:
                        self.logger.error(
                            f"Channel {config.channel_id} not found, skipping"
                        )
                        continue

                    msg = await self.share_post(submission, channel)
                    config.last_known_post_creation = created
                    config.save()

                    RedditPost.create(
                        post_id=submission.id,
                        subreddit=submission.subreddit.display_name,
                        title=submission.title,
                        permalink=submission.permalink,
                        created=submission.created_utc,
                        author=submission.author.name,
                        is_nsfw=submission.over_18,
                        spoiler=submission.spoiler,
                        message_id=msg.id,
                    )

    @reddit_feed_group.command(
        name="subscribe",
        description="Watch a specific subreddit and post new posts to the current channel",
    )
    @is_bot_owner_or_admin()
    async def subscribe(self, interaction: discord.Interaction, subreddit_name: str):
        subreddit_name = subreddit_name.lstrip("/r/")
        reddit_config, created = RedditFeedConfig.get_or_create(
            channel_id=interaction.channel.id,
            subreddit=subreddit_name,
        )
        reddit_config.last_known_post_creation = datetime.datetime.now(
            datetime.timezone.utc
        ).timestamp()
        reddit_config.save()

        subreddit_url = f"https://reddit.com/r/{subreddit_name}"
        embed = discord.Embed(
            title=f"Subscribe to /r/{subreddit_name}",
            description=f"Watching [/r/{subreddit_name}](<{subreddit_url}>) for new posts and sharing them in {interaction.channel.mention}",
            color=discord.Color(0x00FF00),
        )

        await interaction.response.send_message(embed=embed)

    @reddit_feed_group.command(
        name="unsubscribe", description="Stop watching a subreddit"
    )
    @is_bot_owner_or_admin()
    async def unsubscribe(self, interaction: discord.Interaction, subreddit_name: str):
        subreddit_name = subreddit_name.lstrip("/r/")
        reddit_config = RedditFeedConfig.get_or_none(
            channel_id=interaction.channel.id,
            subreddit=subreddit_name,
        )

        subreddit_url = f"https://reddit.com/r/{subreddit_name}"

        if not reddit_config:
            embed = discord.Embed(
                title=f"Unsubscribe from /r/{subreddit_name}",
                description=f"[/r/{subreddit_name}](<{subreddit_url}>) is not being watched in {interaction.channel.mention}",
                color=discord.Color(0xFF0000),
            )
            await interaction.response.send_message(embed=embed)
            return
        reddit_config.delete_instance()

        embed = discord.Embed(
            title=f"Unsubscribe from /r/{subreddit_name}",
            description=f"Stopped watching [/r/{subreddit_name}](<{subreddit_url}>) in {interaction.channel.mention}",
            color=discord.Color(0x00FF00),
        )

        await interaction.response.send_message(embed=embed)

    async def get_subreddit_icon(self, subreddit_name: str) -> str:
        if subreddit_name in self.subreddit_icon_cache:
            return self.subreddit_icon_cache[subreddit_name]

        subreddit = await self.reddit.subreddit(subreddit_name, fetch=True)
        icon = subreddit.community_icon
        if not icon:
            return None

        self.subreddit_icon_cache[subreddit_name] = icon
        return icon

    @commands.command(name="reddittest", description="Test the Reddit feed")
    @is_bot_owner_or_admin()
    async def test(self, ctx: commands.Context):
        subreddit = await self.reddit.subreddit("lancaster")
        async for submission in subreddit.new(limit=1):
            channel = self.bot.get_channel(ctx.channel.id)
            await self.share_post(submission, channel)

    async def share_post(
        self, submission: Submission, channel: TextChannel
    ) -> discord.Message:
        """Share a Reddit post to a channel

        Args:
            submission (Submission): The Reddit post to share
            channel (TextChannel): The channel to share the post to
        """
        permalink = f"https://reddit.com{submission.permalink}"

        embed = discord.Embed(
            title=submission.title,
            url=permalink,
            description=submission.selftext,
            color=discord.Color(0xFF0000),
        )

        nsfw = submission.over_18 or submission.spoiler
        if hasattr(submission, "preview") and not nsfw:
            high_res = submission.preview["images"][0]["source"]["url"]
            embed.set_image(url=high_res)

        author_url = f"https://reddit.com/u/{submission.author}"
        embed.add_field(
            name="Post Author", value=f"[/u/{submission.author}]({author_url})"
        )
        embed.add_field(name="Content Warning", value="NSFW" if nsfw else "None")
        embed.timestamp = datetime.datetime.fromtimestamp(submission.created_utc)

        icon = await self.get_subreddit_icon(submission.subreddit.display_name)
        embed.set_footer(text=f"/r/{submission.subreddit.display_name}", icon_url=icon)

        return await channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(RedditFeed(bot))
