import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from utils.command_utils import is_bot_owner, is_bot_owner_or_admin


class Bot(LancoCog, name="Bot", description="Bot configuration commands"):
    def build_activity_options(self):
        dynamic_options = [
            {"name": "Playing", "value": "playing"},
            {"name": "Listening", "value": "listening"},
            {"name": "Watching", "value": "watching"},
        ]
        return [
            app_commands.Choice(name=option["name"], value=option["value"])
            for option in dynamic_options
        ]

    @app_commands.command(
        name="activity",
        description="Set the bot's activity",
    )
    @is_bot_owner()
    async def choose_activity_type(
        self, interaction: discord.Interaction, option: str, activity: str
    ):
        self.logger.info(f"Setting activity to {option} {activity}")

        if option == "playing":
            await self.bot.change_presence(activity=discord.Game(name=activity))
        elif option == "listening":
            await self.bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening, name=activity
                )
            )
        elif option == "watching":
            await self.bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching, name=activity
                )
            )

        await interaction.response.send_message(
            f"Activity set to {option} {activity}", ephemeral=True
        )

    @choose_activity_type.autocomplete("option")
    async def dynamic_option_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        options = self.build_activity_options()
        return [choice for choice in options if current.lower() in choice.name.lower()]

    @app_commands.command(
        name="setname",
        description="Change the bot's name in the current guild",
    )
    @is_bot_owner_or_admin()
    async def setname(self, interaction: discord.Interaction, name: str):
        await interaction.guild.me.edit(nick=name)
        await interaction.response.send_message(f"Name set to {name}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Bot(bot))
