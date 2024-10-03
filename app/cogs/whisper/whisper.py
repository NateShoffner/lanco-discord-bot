import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands


class Whisper(LancoCog, name="Whisper", description="Whisper commands"):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    @app_commands.command(name="w", description="Whisper a user")
    async def whisper(
        self, interaction: discord.Interaction, user: discord.Member, *, message: str
    ):
        self.logger.info(
            f"Whispering to {user.name}: {message} from {interaction.user.name}"
        )
        if user == interaction.user:
            await interaction.response.send_message(
                "You can't whisper to yourself", ephemeral=True
            )
            return

        if user.bot:
            await interaction.response.send_message(
                "You can't whisper to a bot", ephemeral=True
            )
            return

        guild = interaction.guild

        msg = f"{interaction.user.mention}: {message}"
        if interaction.guild:
            msg += f" in {guild.name}"
        await user.send(msg)
        await interaction.response.send_message(
            f"Whispered {user.mention}", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Whisper(bot))
