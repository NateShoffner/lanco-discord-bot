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
    description="Everbridge cog",
):
    g = app_commands.Group(
        name="everbridge",
        description="Everbridge commands",
    )

    UPDATE_INTERVAL = 10  # seconds

    def __init__(self, bot):
        super().__init__(bot)
        # TODO might want to allow the use of multiple sets of credentials which can be used to isolate different Everbridge accounts
        self.client = EverbridgeClient(
            username=os.getenv("EVERBRIDGE_USERNAME"),
            password=os.getenv("EVERBRIDGE_PASSWORD"),
        )
        self.bot.database.create_tables([EverbridgeConfig])

    async def cog_load(self):
        self.poll.start()

    def cog_unload(self):
        self.poll.cancel()

    @tasks.loop(seconds=UPDATE_INTERVAL)
    async def poll(self):
        """Poll for new Everbridge notifications."""
        self.logger.info("Polling...")
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

    async def get_new_notifications(self):
        """Get new Everbridge notifications."""
        everbridge_configs = EverbridgeConfig.select()
        if not everbridge_configs:
            self.logger.info("No Everbridge configurations found.")
            return

        notifications = await self.client.get_notifications()

        if not notifications:
            self.logger.info("No new notifications found.")
            return

        # reverse the notifs
        notifications.reverse()

        for config in everbridge_configs:
            channel = self.bot.get_channel(config.channel_id)
            if not channel:
                self.logger.warning(f"Channel {config.channel_id} not found.")
                continue

            last_event_date = config.last_event_date

            # For testing
            # last_event_date = datetime.datetime.now() - datetime.timedelta(weeks=4)

            if not last_event_date:
                return  # if no last event date, skip this config

            new_notifications = [
                notification
                for notification in notifications
                if notification.createdAt > last_event_date
            ]

            self.logger.info(
                f"New notifications for channel {config.channel_id}: {len(new_notifications)}"
            )

            if new_notifications:
                for notification in new_notifications:
                    embed = await self.build_notification_embed(notification, config)
                    await channel.send(embed=embed)
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
            channel_id=interaction.channel.id,
            subscription_name=subscription_name,
        )
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
        everbridge_config = EverbridgeConfig.get_or_none(
            channel_id=interaction.channel.id
        )

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
