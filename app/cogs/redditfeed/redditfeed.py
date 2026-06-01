import datetime
import os
import urllib.parse

import asyncpraw
import cachetools
import discord
from asyncpraw.models import Submission
from cogs.lancocog import LancoCog
from discord import TextChannel, app_commands
from discord.ext import commands, tasks
from utils.command_utils import is_bot_owner_or_admin
from utils.file_downloader import FileDownloader
from utils.image_utils import blur_image
from utils.markdown_utils import reddit_to_discord

from .models import RedditFeedConfig, RedditPost


class RedditFeed(LancoCog, name="RedditFeed", description="Reddit feed polling"):
    reddit_feed_group = app_commands.Group(
        name="reddit", description="Poll Reddit for new posts"
    )

    UPDATE_INTERVAL = 10  # seconds
    POST_LIMIT = 25
    HISTORY_WINDOW = 50  # number of recent posts per subreddit to check for updates

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
        self.cache_dir = os.path.join(self.get_cog_data_directory(), "Cache")
        self.file_downloader = FileDownloader()

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

        # build up a map of subreddits to configs for efficiency
        subreddit_channels = {}
        for reddit_config in reddit_configs:
            if reddit_config.subreddit not in subreddit_channels:
                subreddit_channels[reddit_config.subreddit] = []
            subreddit_channels[reddit_config.subreddit].append(reddit_config)

        for sr, configs in subreddit_channels.items():
            self.logger.info(f"Checking for new posts in /r/{sr}")
            subreddit = await self.reddit.subreddit(sr)

            submissions = []
            async for submission in subreddit.new(limit=self.POST_LIMIT):
                submissions.append(submission)
            submissions = sorted(submissions, key=lambda s: s.created_utc)

            # Load recent known posts for this subreddit to check for updates
            recent_posts = list(
                RedditPost.select()
                .where(RedditPost.subreddit == sr)
                .order_by(RedditPost.created.desc())
                .limit(self.HISTORY_WINDOW)
            )
            seen_ids = {p.post_id for p in recent_posts}

            for submission in submissions:
                deleted = submission.selftext == "[deleted]"
                removed = submission.selftext == "[removed]"
                edited = bool(submission.edited)
                author = submission.author.name if submission.author else "[deleted]"

                # Check if we've seen this post before (across all channels)
                existing_posts = [p for p in recent_posts if p.post_id == submission.id]

                for config in configs:
                    existing = next(
                        (
                            p
                            for p in existing_posts
                            if p.channel_id == config.channel_id
                        ),
                        None,
                    )

                    if existing:
                        # Check if anything changed worth updating
                        if (
                            existing.deleted == deleted
                            and existing.removed == removed
                            and existing.edited == edited
                        ):
                            continue

                        # Update the existing Discord message
                        existing.deleted = deleted
                        existing.removed = removed
                        existing.edited = edited
                        existing.comment_count = submission.num_comments
                        existing.score = submission.score
                        existing.last_updated = datetime.datetime.now(
                            datetime.timezone.utc
                        )
                        existing.save()

                        channel = self.bot.get_channel(config.channel_id)
                        if channel:
                            await self.share_post(
                                submission, channel, existing_post=existing
                            )
                        continue

                    # New post — skip if already seen in any channel (ID-based dedup)
                    if submission.id in seen_ids:
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

                    now = datetime.datetime.now(datetime.timezone.utc)
                    RedditPost.create(
                        post_id=submission.id,
                        subreddit=submission.subreddit.display_name,
                        channel_id=config.channel_id,
                        title=submission.title,
                        permalink=submission.permalink,
                        created=submission.created_utc,
                        author=author,
                        is_nsfw=submission.over_18,
                        spoiler=submission.spoiler,
                        deleted=deleted,
                        removed=removed,
                        edited=edited,
                        comment_count=submission.num_comments,
                        score=submission.score,
                        last_updated=now,
                        message_id=msg.id,
                    )

                # Mark as seen after processing all configs for this submission
                seen_ids.add(submission.id)
                for config in configs:
                    config.last_known_post_creation = submission.created_utc
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

    @commands.command(
        name="reddittest2", description="Test the Reddit feed with a specific URL"
    )
    @is_bot_owner_or_admin()
    async def test2(self, ctx: commands.Context):
        url = "https://www.reddit.com/r/lancaster/comments/1rbp3hm/snow_emergency_today_move_your_cars/"
        try:
            submission = await self.reddit.submission(url=url)
            channel = self.bot.get_channel(ctx.channel.id)
            await self.share_post(submission, channel)
        except Exception as e:
            await ctx.send(f"Error: {e}")
            self.logger.error(f"Error in reddittest2: {e}")

    async def share_post(
        self,
        submission: Submission,
        channel: TextChannel,
        existing_post: RedditPost = None,
    ) -> discord.Message:
        """Share or update a Reddit post in a channel."""
        permalink = f"https://reddit.com{submission.permalink}"

        deleted = submission.selftext == "[deleted]"
        removed = submission.selftext == "[removed]"

        # Convert Reddit markdown to Discord-compatible markdown
        selftext = reddit_to_discord(submission.selftext)

        # limit to 4096 characters to avoid Discord embed size limit
        description = selftext[:4096]
        if len(selftext) >= 4096:
            description = f"{description[:4093]}..."

        # limit title to 256 characters
        title = submission.title
        if len(title) >= 256:
            title = f"{title[:253]}..."

        nsfw = submission.over_18 or submission.spoiler
        icon = await self.get_subreddit_icon(submission.subreddit.display_name)

        color = discord.Color(0xFF0000)
        if deleted or removed:
            color = discord.Color(0x808080)

        embed = discord.Embed(
            title=title,
            url=permalink,
            description=description,
            color=color,
        )

        author_name = submission.author.name if submission.author else "[deleted]"
        author_url = f"https://reddit.com/u/{author_name}"
        embed.add_field(name="Post Author", value=f"[/u/{author_name}]({author_url})")
        embed.add_field(name="Content Warning", value="NSFW" if nsfw else "None")
        embed.add_field(
            name="Flair",
            value=(
                f"[{submission.link_flair_text}](https://reddit.com/r/{submission.subreddit.display_name}/?f=flair_name%3A%22{urllib.parse.quote(submission.link_flair_text)}%22)"
                if submission.link_flair_text
                else "None"
            ),
        )
        embed.add_field(name="Comments", value=submission.num_comments)
        embed.add_field(name="Score", value=submission.score)

        if deleted:
            embed.add_field(name="Status", value="🗑️ Deleted")
        elif removed:
            embed.add_field(name="Status", value="🚫 Removed")
        elif submission.edited:
            embed.add_field(name="Status", value="✏️ Edited")

        embed.timestamp = datetime.datetime.fromtimestamp(submission.created_utc)
        embed.set_footer(text=f"/r/{submission.subreddit.display_name}")
        embed.set_thumbnail(url=icon)

        temp_files = []
        manual_blur = False
        file = None

        image_url = None
        if hasattr(submission, "preview"):
            image_url = submission.preview["images"][0]["source"]["url"]
        if hasattr(submission, "media_metadata"):
            if (
                hasattr(submission, "gallery_data")
                and "items" in submission.gallery_data
            ):
                for gallery_item in submission.gallery_data["items"]:
                    media_id = gallery_item["media_id"]
                    item = submission.media_metadata.get(media_id)
                    if item and item["status"] == "valid" and item["e"] == "Image":
                        image_url = item["s"]["u"]
                        break
            else:
                for item in submission.media_metadata.values():
                    if item["status"] == "valid" and item["e"] == "Image":
                        image_url = item["s"]["u"]
                        break

        if image_url and not deleted and not removed:
            if nsfw:
                image_path = await self.file_downloader.download_file(
                    image_url, self.cache_dir
                )
                temp_files.append(image_path)
                blurred_path = self.file_downloader.get_random_filename(
                    image_url, self.cache_dir
                )
                blur_image(image_path, blurred_path, 75)
                temp_files.append(blurred_path)
                filename = os.path.basename(blurred_path)
                file = discord.File(blurred_path, filename=filename)
                manual_blur = True
                embed.set_image(url=f"attachment://{filename}")
            else:
                embed.set_image(url=image_url)

        # Edit existing message or send new one
        if existing_post:
            try:
                msg = await channel.fetch_message(existing_post.message_id)
                await msg.edit(embed=embed)
            except discord.NotFound:
                self.logger.warning(
                    f"Original message {existing_post.message_id} not found, skipping update"
                )
                msg = None
        elif manual_blur:
            msg = await channel.send(embed=embed, file=file)
        else:
            msg = await channel.send(embed=embed)

        for f in temp_files:
            os.remove(f)

        return msg


async def setup(bot):
    await bot.add_cog(RedditFeed(bot))
