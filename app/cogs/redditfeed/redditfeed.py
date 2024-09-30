import datetime
import os

import asyncpraw
import discord
from asyncpraw.models import Submission
from cogs.lancocog import LancoCog
from discord import TextChannel, app_commands
from discord.ext import commands, tasks
from utils.command_utils import is_bot_owner_or_admin

from .models import RedditFeedConfig


class RedditFeed(LancoCog):
    reddit_feed_group = app_commands.Group(
        name="reddit", description="Poll Reddit for new posts"
    )

    UPDATE_INTERVAL = 10  # seconds
    POST_LIMIT = 5  # TODO: make this configurable

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot = bot
        self.bot.database.create_tables([RedditFeedConfig])
        self.reddit = asyncpraw.Reddit(
            client_id=os.getenv("REDDIT_ID"),
            client_secret=os.getenv("REDDIT_SECRET"),
            user_agent="LanCo Discord Bot (by /u/syntack)",
        )

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

                    await self.share_post(submission, channel)
                    config.last_known_post_creation = created
                    config.save()

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

        await interaction.response.send_message(
            f"Watching /r/{subreddit_name} for new posts and posting them to this channel"
        )

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

        if not reddit_config:
            await interaction.response.send_message(
                f"Not watching /r/{subreddit_name} in this channel"
            )
            return
        reddit_config.delete_instance()

        await interaction.response.send_message(f"Stopped watching /r/{subreddit_name}")

    async def share_post(self, submission: Submission, channel: TextChannel) -> None:
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

        embed.add_field(name="Post Author", value=f"/u/{submission.author}")
        embed.add_field(name="Content Warning", value="NSFW" if nsfw else "None")
        embed.timestamp = datetime.datetime.fromtimestamp(submission.created_utc)

        await channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(RedditFeed(bot))
