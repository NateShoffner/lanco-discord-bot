import datetime
import os

import discord
import psutil
from cogs.lancocog import LancoCog
from discord.ext import commands, tasks

from .models import BotGuild, BotMetrics

SNAPSHOT_INTERVAL_SECONDS = 30
MAX_RETAINED_SNAPSHOTS = 2880  # 30s interval * 2880 = 24 hours


class Metrics(
    LancoCog,
    name="Metrics",
    description="Collects and persists bot metrics for the dashboard",
):
    def __init__(self, bot):
        super().__init__(bot)
        self._process = psutil.Process(os.getpid())

    async def cog_load(self):
        self.bot.database.create_tables([BotMetrics, BotGuild], safe=True)
        self.collect_metrics.start()

    @commands.Cog.listener()
    async def on_ready(self):
        """Sync the full guild list on startup."""
        current_ids = {g.id for g in self.bot.guilds}

        # Remove guilds the bot is no longer in
        BotGuild.delete().where(BotGuild.guild_id.not_in(current_ids)).execute()

        # Upsert all current guilds
        for guild in self.bot.guilds:
            BotGuild.insert(guild_id=guild.id, name=guild.name).on_conflict(
                conflict_target=[BotGuild.guild_id],
                update={BotGuild.name: guild.name},
            ).execute()

        self.logger.info(f"Synced {len(self.bot.guilds)} guilds to bot_guilds table.")

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        BotGuild.insert(guild_id=guild.id, name=guild.name).on_conflict(
            conflict_target=[BotGuild.guild_id],
            update={BotGuild.name: guild.name},
        ).execute()
        self.logger.info(f"Joined guild: {guild.name} ({guild.id})")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        BotGuild.delete().where(BotGuild.guild_id == guild.id).execute()
        self.logger.info(f"Left guild: {guild.name} ({guild.id})")

    async def cog_unload(self):
        self.collect_metrics.cancel()

    @tasks.loop(seconds=SNAPSHOT_INTERVAL_SECONDS)
    async def collect_metrics(self):
        try:
            uptime = (datetime.datetime.utcnow() - self.bot.start_time).total_seconds()

            memory_mb = None
            cpu_percent = None
            try:
                memory_mb = self._process.memory_info().rss / 1024 / 1024
                cpu_percent = self._process.cpu_percent(interval=None)
            except Exception:
                pass

            BotMetrics.create(
                latency_ms=round(self.bot.latency * 1000, 2),
                guild_count=len(self.bot.guilds),
                user_count=sum(g.member_count for g in self.bot.guilds),
                uptime_seconds=uptime,
                memory_mb=memory_mb,
                cpu_percent=cpu_percent,
                cog_count=len(self.bot.get_lanco_cogs()),
            )

            # Prune old snapshots beyond retention window
            cutoff = (
                BotMetrics.select(BotMetrics.id)
                .order_by(BotMetrics.id.desc())
                .offset(MAX_RETAINED_SNAPSHOTS)
                .limit(1)
                .scalar()
            )
            if cutoff:
                BotMetrics.delete().where(BotMetrics.id <= cutoff).execute()

        except Exception as e:
            self.logger.error(f"Failed to collect metrics: {e}")

    @collect_metrics.before_loop
    async def before_collect(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Metrics(bot))
