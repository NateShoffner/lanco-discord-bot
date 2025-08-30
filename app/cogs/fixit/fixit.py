import urllib.parse

import aiohttp
import discord
from cogs.lancocog import LancoCog
from discord import TextChannel, app_commands
from discord.ext import commands, tasks
from seeclickfix.client import SeeClickFixClient
from seeclickfix.models.issue import Issue, Status
from utils.command_utils import is_bot_owner_or_admin

from .models import FixItConfig


class FixIt(LancoCog, name="FixIt", description="FixIt issue tracking"):
    g = app_commands.Group(name="fixit", description="Fix it")

    UPDATE_INTERVAL = 30  # seconds

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot.database.create_tables([FixItConfig])
        self.client = SeeClickFixClient()

    async def cog_load(self):
        self.poll.start()

    def cog_unload(self):
        self.poll.cancel()

    @tasks.loop(seconds=UPDATE_INTERVAL)
    async def poll(self):
        """Poll for new issues"""
        self.logger.info("Polling...")
        try:
            await self.get_new_issues()
        except Exception as e:
            self.logger.error(f"Error polling: {e}")

    async def get_new_issues(self):
        """Get new issues and share them to the configured channels"""
        fixit_configs = FixItConfig().select()
        if not fixit_configs:
            return

        params = {
            "min_lat": 40.02961244400919,
            "min_lng": -76.333590881195,
            "max_lat": 40.04702644421361,
            "max_lng": -76.26908911880496,
            "status": [Status.OPEN],
            "page": 1,
        }

        issues_response = await self.client.get_issues(**params)

        for issue in issues_response.issues:
            for fixit_config in fixit_configs:
                if (
                    fixit_config.last_known_issue
                    and issue.id <= fixit_config.last_known_issue
                ):
                    continue

                self.logger.info(f"New FixIt issue: {issue.id} - {issue.summary}")

                fixit_config.last_known_issue = issue.id
                fixit_config.save()

                channel = self.bot.get_channel(fixit_config.channel_id)
                await self.share_issue(issue, channel)

    @g.command(
        name="subscribe",
        description="Watch for new FixIt issues and post them to the current channel",
    )
    @is_bot_owner_or_admin()
    async def subscribe(self, interaction: discord.Interaction):
        fixit_config, created = FixItConfig.get_or_create(
            guild_id=interaction.guild.id, channel_id=interaction.channel.id
        )
        fixit_config.save()

        await interaction.response.send_message("Subscribed to new FixIt issues")

    @g.command(
        name="unsubscribe",
        description="Stop watching for new FixIt issues in this channel",
    )
    @is_bot_owner_or_admin()
    async def unsubscribe(self, interaction: discord.Interaction):
        fixit_config = FixItConfig.get_or_none(
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
        )

        if not fixit_config:
            await interaction.response.send_message("Not subscribed to FixIt issues")
            return
        fixit_config.delete_instance()

        await interaction.response.send_message("Unsubscribed from FixIt issues")

    async def share_issue(self, issue: Issue, channel: TextChannel) -> None:
        """Share a SeeClickFix issue to a channel

        Args:
            issue (Issue): The issue to share
            channel (TextChannel): The channel to share the issue to
        """

        issue_url = f"https://seeclickfix.com/web_portal/KUofSdjUa9TNPzzidPi3yQqw/issues/{issue.id}"

        encoded = urllib.parse.quote(issue.address)
        google_address = f"https://www.google.com/maps/search/?api=1&query={encoded}"

        embed = discord.Embed(
            title=issue.summary,
            url=issue_url,
            description=issue.description,
            color=discord.Color(0xFF0000),
        )

        embed.add_field(name="Issue ID", value=issue.id)
        embed.add_field(name="Status", value=issue.status)
        embed.add_field(
            name="Address", value=f"[{issue.address}]({google_address})", inline=False
        )

        if issue.media:
            embed.set_image(url=issue.media.image_full)

        embed.timestamp = discord.utils.parse_time(issue.created_at)

        await channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(FixIt(bot))
