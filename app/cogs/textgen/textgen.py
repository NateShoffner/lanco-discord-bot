import re
import discord
from discord.ext import commands
from discord import app_commands
from cogs.lancocog import LancoCog
from zalgo_text import zalgo


class TextGen(LancoCog):
    textgen_group = app_commands.Group(
        name="textgen", description="Text generator commands"
    )

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot = bot

    @textgen_group.command(name="zalgo", description="Generate zalgo text")
    async def zalgo(self, interaction: discord.Interaction, text: str):
        zalgo_text = zalgo.zalgo().zalgofy(text)
        await interaction.response.send_message(zalgo_text, ephemeral=True)


async def setup(bot):
    await bot.add_cog(TextGen(bot))
