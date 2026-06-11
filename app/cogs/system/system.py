import asyncio
import datetime
import os
import time
from sys import version_info as sysv
from time import monotonic

import aiohttp
import discord
import psutil
from cogs.lancocog import LancoCog
from discord.ext import commands
from utils.command_utils import is_bot_owner
from utils.dist_utils import get_bot_version, get_commit_hash
from utils.network_utils import get_external_ip

USAGE_API = "https://api.openai.com/v1/organization/usage/completions"
CACHE_TTL = 300  # seconds

# Estimate: ~0.1 mL of water per token (Li et al. 2023, "Making AI Less Thirsty", arxiv.org/abs/2304.03271;
# OpenAI has not published figures - GPT-5 may consume more, treat this as a conservative lower bound)
ML_PER_TOKEN = 0.1


class SystemCog(LancoCog, name="SystemCog", description="System and admin commands"):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self._openai_admin_key = os.getenv("OPENAI_ADMIN_KEY")
        self._openai_project_id = os.getenv("OPENAI_PROJECT_ID")
        self._usage_cache: dict[int, tuple[float, datetime.datetime, dict]] = (
            {}
        )  # days -> (monotonic, fetched_at, data)

    async def cog_load(self):
        await super().cog_load()
        if not self._openai_admin_key:
            self.logger.warning(
                "OPENAI_ADMIN_KEY not set - token usage commands will not work"
            )
        if not self._openai_project_id:
            self.logger.warning(
                "OPENAI_PROJECT_ID not set - usage will reflect entire account, not just this project"
            )

    async def _fetch_usage(self, start_time: int, end_time: int) -> dict | None:
        """Fetch usage data, paginating in 31-day windows to stay within API limits."""
        window = 31 * 86400
        all_buckets = []
        chunk_start = start_time

        headers = {"Authorization": f"Bearer {self._openai_admin_key}"}
        async with aiohttp.ClientSession() as session:
            while chunk_start < end_time:
                chunk_end = min(chunk_start + window, end_time)
                params = {
                    "start_time": chunk_start,
                    "end_time": chunk_end,
                    "bucket_width": "1d",
                    "group_by": "model",
                    "limit": 31,
                }
                if self._openai_project_id:
                    params["project_ids"] = self._openai_project_id
                async with session.get(
                    USAGE_API, params=params, headers=headers
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        self.logger.error(
                            "OpenAI usage API error %s: %s", resp.status, body
                        )
                        return None
                    data = await resp.json()
                    all_buckets.extend(data.get("data", []))
                chunk_start = chunk_end

        return {"data": all_buckets}

    async def _get_usage(self, days: int) -> dict | None:
        """Return cached usage data for the given day range, fetching if stale."""
        cached_at, fetched_at, cached_data = self._usage_cache.get(
            days, (0, None, None)
        )
        if cached_data is not None and (time.monotonic() - cached_at) < CACHE_TTL:
            self.logger.debug("Returning cached usage data for %d days", days)
            return cached_data, fetched_at

        now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        start = now - days * 86400
        data = await self._fetch_usage(start, now)
        if data is not None:
            fetched_at = datetime.datetime.now(datetime.timezone.utc)
            self._usage_cache[days] = (time.monotonic(), fetched_at, data)
        return data, fetched_at

    def _aggregate_usage(self, data: dict) -> tuple[dict[str, dict], int, int]:
        """Returns (per_model totals, grand input tokens, grand output tokens)."""
        by_model: dict[str, dict] = {}
        for bucket in data.get("data", []):
            for result in bucket.get("results", []):
                model = result.get("model") or "unknown"
                inp = result.get("input_tokens", 0) or 0
                out = result.get("output_tokens", 0) or 0
                cached = result.get("input_cached_tokens", 0) or 0
                if model not in by_model:
                    by_model[model] = {"input": 0, "output": 0, "cached": 0}
                by_model[model]["input"] += inp
                by_model[model]["output"] += out
                by_model[model]["cached"] += cached
        total_in = sum(v["input"] for v in by_model.values())
        total_out = sum(v["output"] for v in by_model.values())
        return by_model, total_in, total_out

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

    @discord.app_commands.command(
        name="token-usage", description="Show OpenAI token usage"
    )
    @discord.app_commands.describe(
        days="Number of past days to include (default 30, max 90)"
    )
    @is_bot_owner()
    async def token_usage(self, interaction: discord.Interaction, days: int = 30):
        if not self._openai_admin_key:
            await interaction.response.send_message(
                "OPENAI_ADMIN_KEY is not configured."
            )
            return

        days = max(1, min(days, 90))
        await interaction.response.defer()

        data, fetched_at = await self._get_usage(days)
        if data is None:
            await interaction.followup.send(
                "Failed to fetch usage data. Check logs for details."
            )
            return

        by_model, total_in, total_out = self._aggregate_usage(data)
        if not by_model:
            await interaction.followup.send(
                f"No usage data found for the past {days} day(s)."
            )
            return

        total = total_in + total_out
        embed = discord.Embed(
            title=f"OpenAI Token Usage - Past {days} day(s)",
            description=f"**{total:,}** total tokens  *{total_in:,} in / {total_out:,} out*",
            color=discord.Color.blurple(),
        )

        lines = []
        for model, counts in sorted(
            by_model.items(), key=lambda x: -(x[1]["input"] + x[1]["output"])
        ):
            t = counts["input"] + counts["output"]
            pct = (t / total * 100) if total else 0
            cached_note = (
                f"  *({counts['cached']:,} cached)*" if counts["cached"] else ""
            )
            lines.append(
                f"`{model}`\n"
                f"↑ {counts['input']:,}  ↓ {counts['output']:,}  *{t:,} ({pct:.1f}%)*{cached_note}"
            )
        embed.add_field(name="Model Breakdown", value="\n\n".join(lines), inline=False)
        embed.set_footer(
            text=f"Updated {fetched_at.strftime('%b %d, %Y %I:%M %p')} UTC"
        )

        await interaction.followup.send(embed=embed)

    @token_usage.error
    async def token_usage_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ):
        if isinstance(error, discord.app_commands.CheckFailure):
            await interaction.response.send_message(
                "You don't have permission to use this command."
            )
        else:
            self.logger.error("token_usage error: %s", error)

    @discord.app_commands.command(
        name="token-water", description="Estimate water consumed by OpenAI token usage"
    )
    @discord.app_commands.describe(
        days="Number of past days to include (default 30, max 90)"
    )
    @is_bot_owner()
    async def token_water(self, interaction: discord.Interaction, days: int = 30):
        if not self._openai_admin_key:
            await interaction.response.send_message(
                "OPENAI_ADMIN_KEY is not configured."
            )
            return

        days = max(1, min(days, 90))
        await interaction.response.defer()

        data, fetched_at = await self._get_usage(days)
        if data is None:
            await interaction.followup.send(
                "Failed to fetch usage data. Check logs for details."
            )
            return

        by_model, total_in, total_out = self._aggregate_usage(data)
        if not by_model:
            await interaction.followup.send(
                f"No usage data found for the past {days} day(s)."
            )
            return

        total_tokens = total_in + total_out
        total_ml = total_tokens * ML_PER_TOKEN
        total_liters = total_ml / 1000

        baja_blasts = total_ml / 709  # large Taco Bell Baja Blast (24 oz)
        showers = total_ml / 60_000  # 8-min shower (~60 L)
        turkey_hill_jugs = total_ml / 1_900  # Turkey Hill iced tea half-gallon jug
        longs_park_lake = total_ml / 11_400_000  # Long's Park lake (~3 million gal)
        susquehanna_secs = (
            total_ml / 425_000_000
        )  # seconds of Susquehanna River flow near Lancaster

        def _fmt(n: float) -> str:
            if n == 0:
                return "0"
            if n < 0.0001:
                return f"{n:.2e}"
            if n < 0.01:
                return f"{n:.6f}"
            if n < 1:
                return f"{n:.3f}"
            return f"{n:,.2f}"

        conversions = [
            ("Baja Blasts (large)", baja_blasts),
            ("8-min showers", showers),
            ("Turkey Hill iced tea jugs", turkey_hill_jugs),
            ("Long's Park lakes", longs_park_lake),
            ("seconds of Susquehanna River flow", susquehanna_secs),
        ]

        embed = discord.Embed(
            title=f"Estimated Water Usage - Past {days} day(s)",
            description=f"**{total_liters:,.3f} L** from **{total_tokens:,}** tokens",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="That's roughly...",
            value="\n".join(f"{label}: **{_fmt(val)}**" for label, val in conversions),
            inline=False,
        )

        lines = []
        for model, counts in sorted(
            by_model.items(), key=lambda x: -(x[1]["input"] + x[1]["output"])
        ):
            t = counts["input"] + counts["output"]
            ml = t * ML_PER_TOKEN
            lines.append(f"`{model}`  {ml:,.1f} mL  *({t:,} tokens)*")
        embed.add_field(name="By Model", value="\n".join(lines), inline=False)

        embed.add_field(
            name="Methodology",
            value=(
                f"{ML_PER_TOKEN} mL/token - loosely derived from [Making AI Less Thirsty (Li et al., 2023)](https://arxiv.org/abs/2304.03271).\n\n"
                f"*Actual water consumption depends on data center location, cooling infrastructure, energy source, utilization rate, and model architecture - "
                f"none of which are publicly disclosed by OpenAI. Token count is also a poor proxy for compute, as the same token count can represent vastly "
                f"different amounts of work depending on the model. Treat these numbers as loose illustration, not measurement.*"
            ),
            inline=False,
        )
        embed.set_footer(
            text=f"Updated {fetched_at.strftime('%b %d, %Y %I:%M %p')} UTC"
        )
        await interaction.followup.send(embed=embed)

    @token_water.error
    async def token_water_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ):
        if isinstance(error, discord.app_commands.CheckFailure):
            await interaction.response.send_message(
                "You don't have permission to use this command."
            )
        else:
            self.logger.error("token_water error: %s", error)


async def setup(bot: commands.Bot):
    await bot.add_cog(SystemCog(bot))
