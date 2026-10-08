"""
Everbridge Cog

Description:
This cog integrates with the Everbridge API to fetch and send notifications to Discord channels.
"""

import datetime
import os

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands, tasks
from everbridge import EverbridgeClient
from everbridge.models import Notification
from utils.command_utils import is_bot_owner_or_admin

from .models import EverbridgeConfig


class Everbridge(
    LancoCog,
    name="Everbridge",
    description="Subscribe to Everbridge emergency alert notifications",
):
    g = app_commands.Group(
        name="everbridge",
        description="Everbridge commands",
        guild_only=True,
    )

    UPDATE_INTERVAL = 10  # seconds

    def __init__(self, bot):
        super().__init__(bot)
        # TODO might want to allow the use of multiple sets of credentials which can be used to isolate different Everbridge accounts
        self.client = EverbridgeClient(
            username=os.getenv("EVERBRIDGE_USERNAME"),
            password=os.getenv("EVERBRIDGE_PASSWORD"),
        )
        self._warned_channels: set[int] = set()

    async def cog_load(self):
        await super().cog_load()
        self.bot.database.create_tables([EverbridgeConfig])
        self.start_loop(self.poll)

    def cog_unload(self):
        self.poll.cancel()

    @tasks.loop(seconds=UPDATE_INTERVAL)
    async def poll(self):
        """Poll for new Everbridge notifications."""
        self.logger.debug("Polling...")
        try:
            await self.get_new_notifications()
        except Exception as e:
            self.logger.error(f"Error polling: {e}")

    async def build_notification_embed(
        self, notification: Notification, config: EverbridgeConfig
    ) -> discord.Embed:
        """Build an embed for a notification."""

        embed_description = f"**{notification.title}**\n\n{notification.body}"

        embed = discord.Embed(
            title=config.subscription_name,
            description=embed_description,
            color=discord.Color.red(),
            timestamp=notification.createdAt,
        )
        embed.set_footer(text=f"ID: {notification.id}")
        return embed

    async def newest_notification_date(self) -> datetime.datetime | None:
        """createdAt of the newest notification, as the API represents it."""
        try:
            notifications = await self.client.get_notifications()
        except Exception:
            self.logger.exception("Could not read notifications to seed a watermark")
            return None
        return max((n.createdAt for n in notifications), default=None)

    async def get_new_notifications(self):
        """Get new Everbridge notifications."""
        everbridge_configs = EverbridgeConfig.select()
        if not everbridge_configs:
            self.logger.debug("No Everbridge configurations found.")
            return

        notifications = await self.client.get_notifications()

        if not notifications:
            self.logger.debug("No new notifications found.")
            return

        # Oldest first: the watermark is the last createdAt sent, and the API
        # returns newest first.
        notifications = sorted(notifications, key=lambda n: n.createdAt)

        for config in everbridge_configs:
            channel = self.bot.get_channel(config.channel_id)
            if not channel:
                if config.channel_id not in self._warned_channels:
                    self._warned_channels.add(config.channel_id)
                    self.logger.warning(f"Channel {config.channel_id} not found.")
                continue

            last_event_date = config.last_event_date

            if not last_event_date:
                # a row predating the seeding below; adopt the newest, not the backlog
                config.last_event_date = notifications[-1].createdAt
                config.save()
                self.logger.info(
                    f"Seeded watermark for channel {config.channel_id}; "
                    f"alerts start from the next notification"
                )
                continue

            new_notifications = [
                notification
                for notification in notifications
                if notification.createdAt > last_event_date
            ]

            self.logger.info(
                f"New notifications for channel {config.channel_id}: {len(new_notifications)}"
            )

            for notification in new_notifications:
                try:
                    embed = await self.build_notification_embed(notification, config)
                    await channel.send(embed=embed)
                except Exception:
                    self.logger.exception(
                        f"Failed to send notification {notification.id} to "
                        f"channel {config.channel_id}, skipping it"
                    )
                # advanced even on failure, so one bad alert cannot wedge the rest
                config.last_event_date = notification.createdAt
                config.save()

    @commands.command()
    async def ebtest(self, ctx):
        notifications = await self.client.get_notifications()
        if not notifications:
            await ctx.send("No notifications found.")
            return

        config = EverbridgeConfig.get_or_none(channel_id=ctx.channel.id)
        if not config:
            await ctx.send("No Everbridge configuration found for this channel.")
            return

        notif = notifications[0]  # Get the first notification for testing
        embed = await self.build_notification_embed(notif, config)
        await ctx.send(embed=embed)

    @g.command(name="subscribe", description="Subscribe to Everbridge notifications")
    @is_bot_owner_or_admin()
    async def subscribe(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        subscription_name: str = "Everbridge Subscription",
    ):
        """Subscribe to Everbridge notifications in a specific channel."""
        everbridge_config, created = EverbridgeConfig.get_or_create(
            channel_id=channel.id,
            subscription_name=subscription_name,
        )

        # Seeded, because the poll delivers nothing without a baseline. From the
        # API rather than the clock: its timestamps are naive.
        if created or not everbridge_config.last_event_date:
            everbridge_config.last_event_date = await self.newest_notification_date()
        everbridge_config.save()

        embed = discord.Embed(
            title="Everbridge Subscription",
            description=f"You have subscribed to Everbridge notifications in {channel.mention}.",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed)

    @g.command(
        name="unsubscribe", description="Unsubscribe from Everbridge notifications"
    )
    @is_bot_owner_or_admin()
    async def unsubscribe(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        """Unsubscribe from Everbridge notifications in a specific channel."""
        everbridge_config = EverbridgeConfig.get_or_none(channel_id=channel.id)

        if everbridge_config:
            everbridge_config.delete_instance()
            embed = discord.Embed(
                title="Everbridge Unsubscription",
                description=f"You have unsubscribed from Everbridge notifications in {channel.mention}.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                title="Everbridge Unsubscription",
                description=f"You are not subscribed to Everbridge notifications in {channel.mention}.",
                color=discord.Color.orange(),
            )
            await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Everbridge(bot))
