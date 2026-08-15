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
from utils.dist_utils import get_bot_version, get_commit_hash


class WebServer(
    LancoCog,
    name="webserver",
    description="Embedded HTTP server for bot integrations",
):
    DEFAULT_PORT = 8080

    g = app_commands.Group(name="web", description="Webserver commands")

    def __init__(self, bot):
        super().__init__(bot)
        self.port = int(os.getenv("WEBSERVER_PORT", self.DEFAULT_PORT))
        self._runner: web.AppRunner | None = None

    async def cog_load(self):
        await super().cog_load()
        # Binding a socket needs no gateway connection, so start here rather than
        # from on_ready: cog_load also covers a hot-reload, where the bot is
        # already ready and on_ready will not fire again.
        await self.start_webserver()

    async def cog_unload(self):
        await super().cog_unload()
        # Without this a reload leaves the old runner holding the port, and the
        # replacement cog fails to bind.
        await self.stop_webserver()

    async def handle_status(self, request: web.Request) -> web.Response:
        """Handle the /status endpoint"""

        if not self.bot.is_ready():
            return web.json_response({"Status": "Starting"}, status=503)

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

    @property
    def running(self) -> bool:
        return self._runner is not None

    async def start_webserver(self) -> bool:
        """Start the server. Returns False if it was already running."""
        if self.running:
            self.logger.debug(f"Webserver already running on port {self.port}")
            return False

        app = web.Application()
        app.router.add_get("/status", self.handle_status)
        runner = web.AppRunner(app)
        await runner.setup()
        try:
            await web.TCPSite(runner, "0.0.0.0", self.port).start()
        except OSError as e:
            # Most often the port is already taken by another process
            await runner.cleanup()
            self.logger.error(f"Failed to start webserver on port {self.port}: {e}")
            return False

        self._runner = runner
        self.logger.info(f"Webserver started on port {self.port}")
        return True

    async def stop_webserver(self) -> bool:
        """Stop the server. Returns False if it was not running."""
        if not self.running:
            return False
        # cleanup() shuts down the site and its sockets along with the runner
        await self._runner.cleanup()
        self._runner = None
        self.logger.info("Webserver stopped")
        return True

    async def restart_webserver(self) -> bool:
        await self.stop_webserver()
        return await self.start_webserver()

    @is_bot_owner()
    @g.command(
        name="start",
        description="Start the webserver",
    )
    async def start_webserver_command(self, interaction: discord.Interaction):
        """Start the webserver"""
        await interaction.response.send_message("Starting webserver...", ephemeral=True)
        started = await self.start_webserver()
        embed = discord.Embed(
            title="Webserver started" if started else "Webserver not started",
            description=(
                f"Webserver started on port {self.port}"
                if started
                else f"Already running on port {self.port}, or the port is unavailable"
            ),
            color=discord.Color.green() if started else discord.Color.orange(),
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
        stopped = await self.stop_webserver()
        embed = discord.Embed(
            title="Webserver stopped" if stopped else "Webserver not running",
            description=(
                "Webserver stopped" if stopped else "There was nothing to stop"
            ),
            color=discord.Color.red() if stopped else discord.Color.orange(),
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
        restarted = await self.restart_webserver()
        embed = discord.Embed(
            title="Webserver restarted" if restarted else "Webserver failed to restart",
            description=(
                f"Webserver restarted on port {self.port}"
                if restarted
                else f"Could not bind port {self.port}"
            ),
            color=discord.Color.green() if restarted else discord.Color.red(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(WebServer(bot))
