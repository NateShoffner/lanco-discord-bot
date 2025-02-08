import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands


class Conversions(LancoCog, name="Conversions", description="Conversions cog"):
    conversion_group = app_commands.Group(
        name="conversion", description="Conversion commands"
    )

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    @conversion_group.command(name="temperature", description="Converts temperature")
    async def temperature(
        self, interaction: discord.Interaction, temp: float, unit: str
    ):
        if unit.lower() == "f":
            celsius = (temp - 32) * 5.0 / 9.0
            await interaction.response.send_message(f"{temp}°F is {celsius}°C")
        elif unit.lower() == "c":
            fahrenheit = (temp * 9.0 / 5.0) + 32
            await interaction.response.send_message(f"{temp}°C is {fahrenheit}°F")
        else:
            await interaction.response.send_message("Invalid unit. Use 'f' or 'c'")


async def setup(bot):
    await bot.add_cog(Conversions(bot))
