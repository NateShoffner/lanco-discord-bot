import discord
from cogs.lancocog import LancoCog
from discord.ext import commands
from utils.command_utils import is_bot_owner


class UserCog(LancoCog, name="UserCog", description="User management commands"):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    @discord.app_commands.command(name="optout", description="Opt out of the bot")
    async def optout(self, interaction: discord.Interaction):
        from main import BlacklistedUser

        BlacklistedUser.create(user_id=interaction.user.id)
        await interaction.response.send_message(
            "You have opted out of the bot.", ephemeral=True
        )

    @discord.app_commands.command(name="optin", description="Opt in to the bot")
    async def optin(self, interaction: discord.Interaction):
        from main import BlacklistedUser

        u = BlacklistedUser.get_or_none(user_id=interaction.user.id)
        if not u:
            await interaction.response.send_message(
                "You are already opted in to the bot.", ephemeral=True
            )
            return
        u.delete_instance()
        await interaction.response.send_message(
            "You have opted in to the bot.", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(UserCog(bot))
