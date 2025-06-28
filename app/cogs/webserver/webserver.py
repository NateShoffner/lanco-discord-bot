"""
WebServer Cog

Description:
WebServer cog
"""

import datetime
import os
from sys import version_info as sysv

import discord
from aiohttp import web
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from utils.command_utils import is_bot_owner

from app.utils.dist_utils import get_bot_version, get_commit_hash


class WebServer(
    LancoCog,
    name="webserver",
    description="webserver cog",
):
    PORT = 6969

    g = app_commands.Group(name="web", description="Webserver commands")

    def __init__(self, bot):
        super().__init__(bot)

    async def on_ready(self):
        """Called when the bot is ready"""
        await self.start_webserver()

    async def handle_status(self, request: web.Request) -> web.Response:
        """Handle the /status endpoint"""

        info = await self.bot.application_info()
        application_emojis = await self.bot.fetch_application_emojis()

        commit = get_commit_hash()

        uptime = datetime.datetime.now() - self.bot.start_time
        owner = self.bot.get_user(info.owner.id)
        dict = {
            "Status": "OK",
            "Python Version": f"{sysv.major}.{sysv.minor}.{sysv.micro}",
            "Discord.py Version": f"{discord.__version__}",
            "Guilds": len(self.bot.guilds),
            "Users": len(self.bot.users),
            "Commands": len(self.bot.commands),
            "Slash Commands": len(self.bot.tree.get_commands()),
            "Latency": f"{round(self.bot.latency * 1000)}ms",
            "Dev Mode": f"{'Enabled' if self.bot.dev_mode else 'Disabled'}",
            "Uptime": f"{uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds // 60) % 60}m {uptime.seconds % 60}s",
            "Cogs": len(self.bot.get_lanco_cogs()),
            "Owner": f"{owner.mention if owner else info.owner.global_name}",
            "Commit": commit[:7],
            "Message Cache": len(self.bot.cached_messages),
            "Voice Clients": len(self.bot.voice_clients),
            "Emojis": len(self.bot.emojis),
            "App Emojis": len(application_emojis),
            "Stickers": len(self.bot.stickers),
            "URL Handlers": len(self.bot.url_handlers),
            "Version": f"{get_bot_version()}",
        }

        return web.json_response(dict)

    async def start_webserver(self):
        app = web.Application()
        app.router.add_get("/status", self.handle_status)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.PORT)
        await site.start()
        print(f"Webserver started on port {self.PORT}")

    async def stop_webserver(self):
        app = web.Application()
        runner = web.AppRunner(app)
        await runner.cleanup()

    async def restart_webserver(self):
        await self.stop_webserver()
        await self.start_webserver()

    @is_bot_owner()
    @g.command(
        name="start",
        description="Start the webserver",
    )
    async def start_webserver_command(self, interaction: discord.Interaction):
        """Start the webserver"""
        await interaction.response.send_message("Starting webserver...", ephemeral=True)
        await self.start_webserver()
        embed = discord.Embed(
            title="Webserver started",
            description=f"Webserver started on port {self.PORT}",
            color=discord.Color.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @is_bot_owner()
    @g.command(
        name="stop",
        description="Stop the webserver",
    )
    async def stop_webserver_command(self, interaction: discord.Interaction):
        """Stop the webserver"""
        await interaction.response.send_message("Stopping webserver...", ephemeral=True)
        await self.stop_webserver()
        embed = discord.Embed(
            title="Webserver stopped",
            description="Webserver stopped",
            color=discord.Color.red(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @is_bot_owner()
    @g.command(
        name="restart",
        description="Restart the webserver",
    )
    async def restart_webserver_command(self, interaction: discord.Interaction):
        """Restart the webserver"""
        await interaction.response.send_message(
            "Restarting webserver...", ephemeral=True
        )
        await self.restart_webserver()
        embed = discord.Embed(
            title="Webserver restarted",
            description=f"Webserver restarted on port {self.PORT}",
            color=discord.Color.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(WebServer(bot))
