"""
ScheduledPost Cog

Allows admins and bot owners to schedule one-time or recurring posts
in any channel, with optional embeds and role pings.
"""

import datetime
import uuid

import dateparser
import discord
from cogs.lancocog import LancoCog
from croniter import croniter
from discord import app_commands
from discord.ext import commands, tasks
from utils.command_utils import is_bot_owner_or_admin

from .models import ScheduledPost as ScheduledPostModel


class ScheduledPost(
    LancoCog,
    name="ScheduledPost",
    description="Schedule one-time or recurring posts in any channel",
):
    def __init__(self, bot):
        super().__init__(bot)

    def cog_unload(self):
        self.check_posts.cancel()

    async def cog_load(self):
        self.bot.database.create_tables([ScheduledPostModel])
        self.check_posts.start()

    @tasks.loop(seconds=30)
    async def check_posts(self):
        now = datetime.datetime.now()
        due = ScheduledPostModel.select().where(
            ScheduledPostModel.next_run_at <= now,
            ScheduledPostModel.is_active == True,
        )

        for post in due:
            await self._send_post(post)

            if post.is_recurring:
                cron = croniter(post.cron_expression, now)
                post.next_run_at = cron.get_next(datetime.datetime)
            else:
                post.is_active = False

            post.last_run_at = now
            post.save()

    async def _send_post(self, post: ScheduledPostModel):
        channel = self.bot.get_channel(post.channel_id)
        if not channel:
            self.logger.warning(
                f"Could not find channel {post.channel_id} for scheduled post {post.id}"
            )
            return

        content = None
        if post.role_ping_id:
            content = f"<@&{post.role_ping_id}>"

        embed = None
        if post.embed_title or post.embed_description:
            embed = discord.Embed(
                title=post.embed_title,
                description=post.embed_description,
                color=post.embed_color or discord.Color.blurple().value,
            )

        text = post.message or content
        try:
            await channel.send(content=text, embed=embed)
        except discord.Forbidden:
            self.logger.warning(
                f"Missing permissions to post in channel {post.channel_id}"
            )

    # --- Commands ---

    scheduled = app_commands.Group(
        name="scheduledpost", description="Manage scheduled posts"
    )

    @scheduled.command(name="add", description="Schedule a new post")
    @app_commands.describe(
        channel="Channel to post in",
        message="Text message to send",
        schedule="When to post — cron expression (e.g. '0 9 * * 1') or natural language (e.g. 'every Monday at 9am')",
        recurring="Whether this post should repeat on the schedule",
        embed_title="Optional embed title",
        embed_description="Optional embed description",
        embed_color="Optional embed color as a hex string (e.g. ff0000)",
        role_ping="Optional role to ping",
    )
    @is_bot_owner_or_admin()
    async def add(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        schedule: str,
        message: str = None,
        recurring: bool = True,
        embed_title: str = None,
        embed_description: str = None,
        embed_color: str = None,
        role_ping: discord.Role = None,
    ):
        if not message and not embed_title and not embed_description:
            await interaction.response.send_message(
                "You must provide at least a message or an embed title/description.",
                ephemeral=True,
            )
            return

        # Parse schedule — try cron first, then natural language
        cron_expr, next_run = self._parse_schedule(schedule, recurring)
        if not cron_expr or not next_run:
            await interaction.response.send_message(
                "Could not parse the schedule. Try a cron expression like `0 9 * * 1` "
                "or natural language like `every Monday at 9am`.",
                ephemeral=True,
            )
            return

        color_int = None
        if embed_color:
            try:
                color_int = int(embed_color.lstrip("#"), 16)
            except ValueError:
                await interaction.response.send_message(
                    "Invalid color. Use a hex string like `ff0000`.", ephemeral=True
                )
                return

        ScheduledPostModel.create(
            id=uuid.uuid4(),
            guild_id=interaction.guild.id,
            channel_id=channel.id,
            created_by=interaction.user.id,
            message=message,
            embed_title=embed_title,
            embed_description=embed_description,
            embed_color=color_int,
            role_ping_id=role_ping.id if role_ping else None,
            cron_expression=cron_expr,
            next_run_at=next_run,
            is_recurring=recurring,
            is_active=True,
        )

        formatted_next = next_run.strftime("%B %d, %Y at %I:%M %p")
        recur_label = "Recurring" if recurring else "One-time"
        await interaction.response.send_message(
            f"✅ {recur_label} post scheduled in {channel.mention}.\n"
            f"**Next run:** {formatted_next}\n"
            f"**Schedule:** `{cron_expr}`",
            ephemeral=True,
        )

    @scheduled.command(
        name="list", description="List all scheduled posts in this server"
    )
    @is_bot_owner_or_admin()
    async def list_posts(self, interaction: discord.Interaction):
        posts = ScheduledPostModel.select().where(
            ScheduledPostModel.guild_id == interaction.guild.id,
            ScheduledPostModel.is_active == True,
        )

        if not posts:
            await interaction.response.send_message(
                "No active scheduled posts.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Scheduled Posts",
            color=discord.Color.blurple(),
        )

        for post in posts:
            channel = interaction.guild.get_channel(post.channel_id)
            channel_name = channel.mention if channel else f"#{post.channel_id}"
            next_run = post.next_run_at.strftime("%b %d, %Y %I:%M %p")
            recur_label = "🔁 Recurring" if post.is_recurring else "1️⃣ One-time"

            preview = (
                post.message
                or post.embed_title
                or post.embed_description
                or "*(embed)*"
            )
            if len(preview) > 80:
                preview = preview[:77] + "..."

            embed.add_field(
                name=f"`{str(post.id)[:8]}` — {channel_name}",
                value=(
                    f"{recur_label} • `{post.cron_expression}`\n"
                    f"**Next:** {next_run}\n"
                    f"**Preview:** {preview}"
                ),
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @scheduled.command(name="delete", description="Delete a scheduled post by ID")
    @app_commands.describe(
        post_id="The post ID (first 8 characters shown in /scheduledpost list)"
    )
    @is_bot_owner_or_admin()
    async def delete(self, interaction: discord.Interaction, post_id: str):
        try:
            post = (
                ScheduledPostModel.select()
                .where(
                    ScheduledPostModel.guild_id == interaction.guild.id,
                    ScheduledPostModel.id.cast("TEXT").startswith(post_id),
                )
                .get()
            )
        except ScheduledPostModel.DoesNotExist:
            await interaction.response.send_message(
                f"No scheduled post found with ID starting with `{post_id}`.",
                ephemeral=True,
            )
            return

        post.delete_instance()
        await interaction.response.send_message(
            f"✅ Scheduled post `{post_id}` deleted.", ephemeral=True
        )

    @scheduled.command(name="pause", description="Pause a scheduled post")
    @app_commands.describe(
        post_id="The post ID (first 8 characters shown in /scheduledpost list)"
    )
    @is_bot_owner_or_admin()
    async def pause(self, interaction: discord.Interaction, post_id: str):
        try:
            post = (
                ScheduledPostModel.select()
                .where(
                    ScheduledPostModel.guild_id == interaction.guild.id,
                    ScheduledPostModel.id.cast("TEXT").startswith(post_id),
                )
                .get()
            )
        except ScheduledPostModel.DoesNotExist:
            await interaction.response.send_message(
                f"No scheduled post found with ID starting with `{post_id}`.",
                ephemeral=True,
            )
            return

        post.is_active = False
        post.save()
        await interaction.response.send_message(
            f"⏸️ Scheduled post `{post_id}` paused.", ephemeral=True
        )

    @scheduled.command(name="resume", description="Resume a paused scheduled post")
    @app_commands.describe(
        post_id="The post ID (first 8 characters shown in /scheduledpost list)"
    )
    @is_bot_owner_or_admin()
    async def resume(self, interaction: discord.Interaction, post_id: str):
        try:
            post = (
                ScheduledPostModel.select()
                .where(
                    ScheduledPostModel.guild_id == interaction.guild.id,
                    ScheduledPostModel.id.cast("TEXT").startswith(post_id),
                )
                .get()
            )
        except ScheduledPostModel.DoesNotExist:
            await interaction.response.send_message(
                f"No scheduled post found with ID starting with `{post_id}`.",
                ephemeral=True,
            )
            return

        post.is_active = True
        post.save()
        await interaction.response.send_message(
            f"▶️ Scheduled post `{post_id}` resumed.", ephemeral=True
        )

    def _parse_schedule(self, schedule: str, recurring: bool):
        """
        Parse a schedule string into a (cron_expression, next_run_at) tuple.
        Tries cron syntax first, then falls back to natural language.
        For one-time posts, builds a one-shot cron from the parsed datetime.
        """
        now = datetime.datetime.now()

        # Try as a cron expression directly
        if croniter.is_valid(schedule):
            cron = croniter(schedule, now)
            next_run = cron.get_next(datetime.datetime)
            return schedule, next_run

        # Try natural language
        parsed = dateparser.parse(schedule, settings={"PREFER_DATES_FROM": "future"})
        if parsed and parsed > now:
            # Build a cron expression from the parsed time
            if recurring:
                # Default recurrence: weekly on that day/time
                cron_expr = f"{parsed.minute} {parsed.hour} * * {parsed.weekday()}"
            else:
                # One-shot: exact date/time
                cron_expr = (
                    f"{parsed.minute} {parsed.hour} {parsed.day} {parsed.month} *"
                )
            return cron_expr, parsed

        return None, None


async def setup(bot):
    await bot.add_cog(ScheduledPost(bot))
