import asyncio
import datetime
import os
from sys import version_info as sysv
from time import monotonic

import discord
import psutil
from cogs.lancocog import LancoCog
from discord.ext import commands
from utils.command_utils import is_bot_owner
from utils.dist_utils import get_bot_version, get_commit_hash
from utils.network_utils import get_external_ip


class SystemCog(LancoCog, name="SystemCog", description="System and admin commands"):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    @discord.app_commands.command(name="ping", description="Ping the bot")
    async def ping(self, interaction: discord.Interaction):
        lat = round(self.bot.latency * 1000)
        embed = discord.Embed(title="🏓 Pong!", color=0x00FF00)
        embed.add_field(name="Bot Latency", value=f"{lat}ms", inline=False)

        start = monotonic()
        msg = await interaction.response.send_message(embed=embed)
        end = monotonic()

        response_msg = await interaction.original_response()
        embed.add_field(
            name="Message Latency",
            value=f"{round((end - start) * 1000)}ms",
            inline=False,
        )
        await response_msg.edit(embed=embed)

    @discord.app_commands.command(name="info", description="Show bot info")
    async def info(self, interaction: discord.Interaction):
        info = await self.bot.application_info()

        desc = f"{self.bot.user.name} is a general-purpose Discord bot tailored for Lancaster County, PA Discord servers.\n\n"
        links = {
            "Homepage": "https://lancobot.dev",
            "GitHub": "https://github.com/NateShoffner/lanco-discord-bot",
            "Privacy Policy": "https://lancobot.dev/privacy",
            "Terms of Service": "https://lancobot.dev/terms",
        }
        for name, url in links.items():
            desc += f"[{name}]({url})\n"

        embed = discord.Embed(
            title=f"{self.bot.user.name} Info", description=desc, color=0x00FF00
        )

        uptime = datetime.datetime.now() - self.bot.start_time
        uptime_str = f"{uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds // 60) % 60}m {uptime.seconds % 60}s"

        owner_str = "Unknown"
        if info.owner:
            owner_str = info.owner.name
        if info.team:
            owner_str = info.team.name

        commit = get_commit_hash()
        github = os.getenv("GITHUB_REPO")
        version_value = (
            f"v{get_bot_version()} - [{commit[:7]}]({github}/commit/{commit})"
            if github
            else f"v{get_bot_version()} - {commit[:7]}"
        )

        embed.add_field(name="Servers", value=str(len(self.bot.guilds)))
        embed.add_field(name="Users", value=str(len(self.bot.users)))
        embed.add_field(name="Uptime", value=uptime_str)
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms")
        embed.add_field(name="Owner", value=owner_str)
        embed.add_field(name="Version", value=version_value)

        embed.set_footer(
            text=f"Discord.py v{discord.__version__} • Python {sysv.major}.{sysv.minor}.{sysv.micro}",
            icon_url="https://lancobot.dev/discord.py.png",
        )

        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(name="diag", description="Show bot diagnostics")
    @is_bot_owner()
    async def diag(self, interaction: discord.Interaction):
        channels = list(self.bot.get_all_channels())
        text_channels = sum(1 for c in channels if isinstance(c, discord.TextChannel))
        voice_channels = sum(1 for c in channels if isinstance(c, discord.VoiceChannel))

        memory_usage = cpu_usage = "N/A"
        pid = None
        try:
            pid = os.getpid()
            process = psutil.Process(pid)
            memory_usage = f"{process.memory_info().rss / 1024 / 1024:.2f} MB"
            cpu_usage = f"{await asyncio.to_thread(psutil.cpu_percent, interval=1)}%"
        except Exception as e:
            self.logger.error(f"Failed to get memory/cpu usage: {e}")

        application_emojis = await self.bot.fetch_application_emojis()

        embed = discord.Embed(title="Bot Diagnostics", color=0x00FF00)
        embed.add_field(
            name="Channels",
            value=f"Total: {len(channels)}\nText: {text_channels}\nVoice: {voice_channels}",
        )
        embed.add_field(
            name="Commands",
            value=f"Normal: {len(self.bot.commands)}\nSlash: {len(self.bot.tree.get_commands())}",
        )
        embed.add_field(
            name="Assets",
            value=f"Emojis: {len(self.bot.emojis)}\nApp Emojis: {len(application_emojis)}\nStickers: {len(self.bot.stickers)}",
        )
        embed.add_field(
            name="Process", value=f"RAM: {memory_usage}\nCPU: {cpu_usage}\nPID: {pid}"
        )
        embed.add_field(name="Cogs", value=str(len(self.bot.get_lanco_cogs())))
        embed.add_field(
            name="Dev Mode", value="Enabled" if self.bot.dev_mode else "Disabled"
        )
        embed.add_field(name="Message Cache", value=str(len(self.bot.cached_messages)))
        embed.add_field(name="Voice Clients", value=str(len(self.bot.voice_clients)))
        embed.add_field(name="URL Handlers", value=str(len(self.bot.url_handlers)))

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.app_commands.command(name="dbinfo", description="Show database info")
    @is_bot_owner()
    async def dbinfo(self, interaction: discord.Interaction):
        from db import database_proxy

        embed = discord.Embed(title="Database Info", color=0x00FF00)

        db = database_proxy.obj
        db_size = 0
        db_type_name = type(db).__name__

        try:
            if "Sqlite" in db_type_name:
                db_size = os.path.getsize(db.database)
            else:
                cursor = db.execute_sql(
                    "SELECT SUM(data_length + index_length) FROM information_schema.tables WHERE table_schema = DATABASE();"
                )
                db_size = cursor.fetchone()[0] or 0
        except Exception as e:
            self.logger.error(f"Failed to get db size: {e}")

        embed.add_field(name="Type", value=db_type_name, inline=False)
        embed.add_field(
            name="Size", value=f"{db_size / 1024 / 1024:.2f} MB", inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.app_commands.command(name="block", description="Block a user")
    @commands.is_owner()
    async def block(
        self, interaction: discord.Interaction, user: discord.User, reason: str
    ):
        from main import BlacklistedUser

        BlacklistedUser.create(user_id=user.id, reason=reason)
        await interaction.response.send_message(
            f"Blocked {user.mention} for {reason}", ephemeral=True
        )

    @discord.app_commands.command(name="unblock", description="Unblock a user")
    @commands.is_owner()
    async def unblock(self, interaction: discord.Interaction, user: discord.User):
        from main import BlacklistedUser

        u = BlacklistedUser.get_or_none(user_id=user.id)
        if not u:
            await interaction.response.send_message(
                f"{user.mention} is not blocked", ephemeral=True
            )
            return
        u.delete_instance()
        await interaction.response.send_message(
            f"Unblocked {user.mention}", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SystemCog(bot))
