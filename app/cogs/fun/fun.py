from cogs.lancocog import LancoCog
from discord import app_commands


class Fun(LancoCog, name="Fun", description="Fun commands"):
    fun_group = app_commands.Group(
        name="fun",
        description="Fun commands",
    )

    @fun_group.command(name="clap", description="Clapify your text")
    async def clap(self, interaction, *, text: str):
        # if just one word, add a clap emoji between each letter
        if len(text.split()) == 1:
            await interaction.response.send_message(" 👏 ".join(text))
        else:
            await interaction.response.send_message(text.replace(" ", " 👏 "))


async def setup(bot):
    await bot.add_cog(Fun(bot))
