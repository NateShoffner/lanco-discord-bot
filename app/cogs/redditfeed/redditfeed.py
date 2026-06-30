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
    STATE_CHECK_INTERVAL = (
        120  # seconds — how often to actively check recent posts for state changes
    )
    POST_LIMIT = 100
    STATE_WINDOW_MINUTES = (
        120  # only check posts made within this window for state changes
    )

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
        # In-memory seen set so SqliteQueueDatabase write-queue latency can't
        # cause re-posts between poll cycles. Seeded from DB on first poll.
        self._seen_ids: dict[str, set[str]] = {}  # subreddit -> set of post_ids
        self._seen_ids_loaded: set[str] = set()  # subreddits whose DB rows are loaded

    async def cog_load(self):
        self.poll.start()
        self.check_post_states.start()

    def cog_unload(self):
        self.poll.cancel()
        self.check_post_states.cancel()

    @tasks.loop(seconds=UPDATE_INTERVAL)
    async def poll(self):
        """Poll for new posts in watched subreddits"""
        self.logger.info("Polling...")
        try:
            await self.get_new_posts()
        except Exception as e:
            self.logger.error(f"Error polling: {e}")

    @tasks.loop(seconds=10)
    async def check_post_states(self):
        """Actively fetch recent posts by ID to catch edits and removals."""
        try:
            await self.update_post_states()
        except Exception as e:
            self.logger.error(f"Error checking post states: {e}")

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
            self.logger.info(f"[{sr}] Polling {len(configs)} channel config(s)")
            subreddit = await self.reddit.subreddit(sr)

            submissions = []
            async for submission in subreddit.new(limit=self.POST_LIMIT):
                submissions.append(submission)
            submissions = sorted(submissions, key=lambda s: s.created_utc)
            self.logger.info(
                f"[{sr}] Fetched {len(submissions)} submissions from Reddit"
            )

            # Seed in-memory seen set from DB once per subreddit, then keep it
            # updated in-process so write-queue latency can't cause re-posts.
            if sr not in self._seen_ids_loaded:
                self._seen_ids[sr] = set(
                    row[0]
                    for row in RedditPost.select(RedditPost.post_id)
                    .where(RedditPost.subreddit == sr.lower())
                    .tuples()
                )
                self._seen_ids_loaded.add(sr)
            seen_ids = self._seen_ids.setdefault(sr, set())
            self.logger.info(f"[{sr}] {len(seen_ids)} known post IDs in DB")

            new_count = sum(1 for s in submissions if s.id not in seen_ids)
            self.logger.info(f"[{sr}] {new_count} new post(s) to process")

            for submission in submissions:
                # Skip already seen posts — state changes handled by check_post_states
                if submission.id in seen_ids:
                    continue

                # Skip posts older than the last known post creation for any config
                # This prevents backfilling old content on restarts
                min_timestamp = min(
                    (
                        c.last_known_post_creation
                        for c in configs
                        if c.last_known_post_creation
                    ),
                    default=None,
                )
                if min_timestamp and submission.created_utc <= min_timestamp:
                    continue

                # New post — share to all configured channels
                author = submission.author.name if submission.author else "[deleted]"
                deleted = submission.selftext == "[deleted]"
                removed = submission.selftext == "[removed]"
                edited = bool(submission.edited)
                permalink = f"https://reddit.com{submission.permalink}"

                self.logger.info(
                    f'[{sr}] New post: {submission.id} — "{submission.title[:60]}" {permalink}'
                )

                for config in configs:
                    self.logger.info(
                        f"[{sr}] Sharing post {submission.id} to channel {config.channel_id}"
                    )

                    channel = self.bot.get_channel(config.channel_id)
                    if not channel:
                        self.logger.error(
                            f"[{sr}] Channel {config.channel_id} not found, skipping"
                        )
                        continue

                    msg = await self.share_post(submission, channel)
                    self.logger.info(
                        f"[{sr}] Posted {submission.id} to channel {config.channel_id} as message {msg.id}"
                    )

                    now = datetime.datetime.now(datetime.timezone.utc)
                    RedditPost.create(
                        post_id=submission.id,
                        subreddit=submission.subreddit.display_name.lower(),
                        channel_id=config.channel_id,
                        title=submission.title,
                        permalink=submission.permalink,
                        created=submission.created_utc,
                        author=author,
                        is_nsfw=submission.over_18,
                        spoiler=submission.spoiler,
                        deleted=deleted,
                        removed=removed,
                        edited=False,  # always False on first insert; set True on update
                        comment_count=submission.num_comments,
                        score=submission.score,
                        last_updated=now,
                        message_id=msg.id,
                    )
                    config.last_known_post_creation = submission.created_utc
                    config.save()

                # Mark as seen
                seen_ids.add(submission.id)
                self.logger.info(f"[{sr}] Marked {submission.id} as seen")

    async def update_post_states(self):
        """Actively fetch recent posts by ID to detect edits and removals."""
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            minutes=self.STATE_WINDOW_MINUTES
        )
        cutoff_ts = cutoff.timestamp()

        # Only check posts for subreddits that still have active configs
        active_subreddits = set(
            row[0].lower()
            for row in RedditFeedConfig.select(RedditFeedConfig.subreddit).tuples()
        )

        recent_posts = list(
            RedditPost.select().where(
                RedditPost.created >= cutoff_ts,
                RedditPost.subreddit << active_subreddits,
                RedditPost.deleted == False,
                RedditPost.removed == False,
            )
        )

        if not recent_posts:
            return

        # Group by subreddit for batched fetching
        by_subreddit = {}
        for post in recent_posts:
            by_subreddit.setdefault(post.subreddit, []).append(post)

        for sr, posts in by_subreddit.items():
            self.logger.info(
                f"[{sr}] Checking state of {len(posts)} recent post(s) via ID fetch"
            )

            # Fetch all posts in a single API call using fullnames (t3_ prefix)
            fullnames = [f"t3_{p.post_id}" for p in posts]
            submissions = {}
            async for submission in self.reddit.info(fullnames=fullnames):
                submissions[submission.id] = submission

            for post in posts:
                submission = submissions.get(post.post_id)
                if not submission:
                    continue

                deleted = submission.selftext == "[deleted]"
                removed = submission.selftext == "[removed]"
                edited = bool(submission.edited)

                if (
                    post.deleted == deleted
                    and post.removed == removed
                    and post.edited == edited
                ):
                    continue

                self.logger.info(
                    f"[{sr}] Post {post.post_id} state changed — "
                    f"deleted={deleted} removed={removed} edited={edited}"
                )

                post.deleted = deleted
                post.removed = removed
                post.edited = edited
                post.comment_count = submission.num_comments
                post.score = submission.score
                post.last_updated = datetime.datetime.now(datetime.timezone.utc)
                post.save()

                channel = self.bot.get_channel(post.channel_id)
                if channel:
                    await self.share_post(submission, channel, existing_post=post)
                else:
                    self.logger.warning(
                        f"[{sr}] Channel {post.channel_id} not found for post {post.post_id}, cannot update message"
                    )

    @reddit_feed_group.command(
        name="subscribe",
        description="Watch a specific subreddit and post new posts to the current channel",
    )
    @is_bot_owner_or_admin()
    async def subscribe(self, interaction: discord.Interaction, subreddit_name: str):
        subreddit_name = subreddit_name.lstrip("/r/").lower()
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
        subreddit_name = subreddit_name.lstrip("/r/").lower()
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

        author_name = submission.author.name if submission.author else None
        if author_name and author_name != "[deleted]":
            author_value = f"[/u/{author_name}](https://reddit.com/u/{author_name})"
        else:
            author_value = "[deleted]"
        embed.add_field(name="Post Author", value=author_value)
        embed.add_field(name="Content Warning", value="NSFW" if nsfw else "None")
        embed.add_field(
            name="Flair",
            value=(
                f"[{submission.link_flair_text}](https://reddit.com/r/{submission.subreddit.display_name}/?f=flair_name%3A%22{urllib.parse.quote(submission.link_flair_text)}%22)"
                if submission.link_flair_text
                else "None"
            ),
        )

        # Status field — only shown when something has changed
        if deleted:
            embed.add_field(name="Status", value="Deleted")
        elif removed:
            embed.add_field(name="Status", value="Removed")
        elif submission.edited:
            embed.add_field(name="Status", value="Edited")

        embed.timestamp = datetime.datetime.fromtimestamp(submission.created_utc)

        footer_parts = [f"/r/{submission.subreddit.display_name}"]
        points = (
            f"{submission.score} point"
            if submission.score == 1
            else f"{submission.score} points"
        )
        comments = (
            f"{submission.num_comments} comment"
            if submission.num_comments == 1
            else f"{submission.num_comments} comments"
        )
        footer_parts.append(f"{points} · {comments}")
        if submission.edited:
            edited_at = datetime.datetime.fromtimestamp(submission.edited).strftime(
                "%b %d at %I:%M %p"
            )
            footer_parts.append(f"Edited {edited_at}")
        embed.set_footer(text=" · ".join(footer_parts))
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
