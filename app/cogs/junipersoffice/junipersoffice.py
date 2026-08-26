"""
Junipers Office Cog

Tracks how long the fish in Juniper's office fish tank have managed to stay
alive, along with the running body count and the best streak so far.
"""

import datetime

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from utils.command_utils import is_bot_owner_or_admin

from .models import FishTankConfig


class JunipersOffice(
    LancoCog,
    name="JunipersOffice",
    description="Days since the last fish death in Juniper's office",
):
    g = app_commands.Group(
        name="junicide",
        description="Juniper's office fish tank",
        guild_only=True,
    )

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    async def cog_load(self):
        await super().cog_load()
        self.bot.database.create_tables([FishTankConfig])

    def get_config(self, guild_id: int) -> FishTankConfig:
        config, _ = FishTankConfig.get_or_create(guild_id=guild_id)
        return config

    def get_streak(self, config: FishTankConfig) -> int | None:
        """Whole days since the last death, or None if nothing is recorded yet."""
        if not config.last_death_at:
            return None
        return (datetime.datetime.now() - config.last_death_at).days

    def get_record(self, config: FishTankConfig) -> int:
        """The best streak, including one that is still running."""
        streak = self.get_streak(config)
        if streak is None:
            return config.record_days
        return max(config.record_days, streak)

    def build_status_embed(self, config: FishTankConfig) -> discord.Embed:
        streak = self.get_streak(config)

        if streak is None:
            headline = "No deaths on record. The fish are winning (for now)."
            color = discord.Color.greyple()
        elif streak == 0:
            headline = "**0 days** since the last fish death. 🪦"
            color = discord.Color.red()
        else:
            unit = "day" if streak == 1 else "days"
            headline = f"**{streak} {unit}** since the last fish death."
            color = discord.Color.orange() if streak < 7 else discord.Color.green()

        embed = discord.Embed(
            title="🐠 Juniper's Office Fish Tank",
            description=headline,
            color=color,
        )
        embed.add_field(name="Total deaths", value=str(config.total_deaths))
        embed.add_field(name="Record", value=f"{self.get_record(config)} days")
        if config.last_death_at:
            timestamp = int(config.last_death_at.timestamp())
            embed.add_field(name="Last death", value=f"<t:{timestamp}:R>", inline=False)
        return embed

    @g.command(name="status", description="Days since the last fish death")
    async def status(self, interaction: discord.Interaction):
        config = self.get_config(interaction.guild.id)
        await interaction.response.send_message(embed=self.build_status_embed(config))

    @g.command(name="death", description="Record a fish death, resetting the counter")
    @is_bot_owner_or_admin()
    async def death(self, interaction: discord.Interaction):
        config = self.get_config(interaction.guild.id)

        streak = self.get_streak(config)
        broken_record = False
        if streak is not None and streak > config.record_days:
            config.record_days = streak
            broken_record = True

        config.total_deaths += 1
        config.last_death_at = datetime.datetime.now()
        config.save()

        lines = ["🪦 Another one down. The counter is back to **0 days**."]
        if streak is not None:
            unit = "day" if streak == 1 else "days"
            lines.append(f"That streak lasted **{streak} {unit}**.")
            if broken_record:
                lines.append("A new record, for whatever that's worth.")
        lines.append(f"Total deaths: **{config.total_deaths}**")

        await interaction.response.send_message("\n".join(lines))

    @g.command(name="set", description="Correct the fish tank numbers")
    @app_commands.describe(
        days="Days since the last death",
        total="Total number of fish deaths",
        record="Longest streak without a death, in days",
    )
    @is_bot_owner_or_admin()
    async def set_values(
        self,
        interaction: discord.Interaction,
        days: app_commands.Range[int, 0] = None,
        total: app_commands.Range[int, 0] = None,
        record: app_commands.Range[int, 0] = None,
    ):
        if days is None and total is None and record is None:
            await interaction.response.send_message(
                "Give me at least one of `days`, `total`, or `record` to set.",
                ephemeral=True,
            )
            return

        config = self.get_config(interaction.guild.id)
        changes = []

        if days is not None:
            config.last_death_at = datetime.datetime.now() - datetime.timedelta(
                days=days
            )
            changes.append(f"days since last death → **{days}**")
        if total is not None:
            config.total_deaths = total
            changes.append(f"total deaths → **{total}**")
        if record is not None:
            config.record_days = record
            changes.append(f"record → **{record} days**")

        config.save()

        await interaction.response.send_message(
            "Updated: " + ", ".join(changes), ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(JunipersOffice(bot))
