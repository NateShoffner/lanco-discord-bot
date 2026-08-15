"""
WebServer Cog

Description:
WebServer cog
"""

import datetime
import math
import os
import secrets
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

    def _uptime_seconds(self) -> int:
        return int((datetime.datetime.now() - self.bot.start_time).total_seconds())

    def _latency_ms(self) -> int | None:
        # Latency is nan until the first heartbeat, which is not valid JSON for
        # strict parsers, so report null instead.
        latency = self.bot.latency
        if math.isnan(latency):
            return None
        return round(latency * 1000)

    async def handle_health(self, request: web.Request) -> web.Response:
        """Unauthenticated liveness probe.

        Deliberately cheap: no Discord API calls, so hammering it cannot burn
        the bot's REST rate limit. The status code is the signal, 200 once the
        gateway is connected and 503 before that.
        """
        ready = self.bot.is_ready()
        return web.json_response(
            {
                "status": "ok" if ready else "starting",
                "uptime_seconds": self._uptime_seconds(),
                "latency_ms": self._latency_ms(),
            },
            status=200 if ready else 503,
        )

    def _token_matches(self, request: web.Request, token: str) -> bool:
        scheme, _, value = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer":
            return False
        return secrets.compare_digest(value, token)

    async def handle_status(self, request: web.Request) -> web.Response:
        """Detailed status, gated behind WEBSERVER_TOKEN.

        Fails closed: with no token configured the endpoint stays off rather
        than publishing this to anyone who finds the port.
        """
        token = os.getenv("WEBSERVER_TOKEN", "")
        if not token:
            return web.json_response(
                {"error": "WEBSERVER_TOKEN is not set, /status is disabled"},
                status=503,
            )
        if not self._token_matches(request, token):
            return web.json_response({"error": "unauthorized"}, status=401)

        ready = self.bot.is_ready()
        return web.json_response(
            {
                "status": "ok" if ready else "starting",
                "ready": ready,
                "uptime_seconds": self._uptime_seconds(),
                "latency_ms": self._latency_ms(),
                "guilds": len(self.bot.guilds),
                # Cache size, not a real user count
                "cached_users": len(self.bot.users),
                "commands": len(self.bot.commands),
                "slash_commands": len(self.bot.tree.get_commands()),
                "cogs_loaded": len(self.bot.extensions),
                "cogs_failed": sorted(getattr(self.bot, "failed_cogs", {})),
                "message_cache": len(self.bot.cached_messages),
                "url_handlers": len(self.bot.url_handlers),
                "dev_mode": self.bot.dev_mode,
                "version": get_bot_version(),
                "commit": (get_commit_hash() or "unknown")[:7],
                "python_version": f"{sysv.major}.{sysv.minor}.{sysv.micro}",
                "discordpy_version": discord.__version__,
            }
        )

    @property
    def running(self) -> bool:
        return self._runner is not None

    async def start_webserver(self) -> bool:
        """Start the server. Returns False if it was already running."""
        if self.running:
            self.logger.debug(f"Webserver already running on port {self.port}")
            return False

        app = web.Application()
        app.router.add_get("/health", self.handle_health)
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
