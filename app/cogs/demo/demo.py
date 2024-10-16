import asyncio

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from utils.channel_lock import command_channel_lock


class Demo(LancoCog, name="Demo", description="Demo cog"):

    def build_options(self):
        dynamic_options = [
            {"name": "Dynamic Option 1", "value": "dynamic1"},
            {"name": "Dynamic Option 2", "value": "dynamic2"},
            {"name": "Dynamic Option 3", "value": "dynamic3"},
        ]
        return [
            app_commands.Choice(name=option["name"], value=option["value"])
            for option in dynamic_options
        ]

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        # self.register_context_menu(
        #    name="Test Menu", callback=self.ctx_menu, errback=self.ctx_menu_error
        # )

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info("Hello, world!")

    @commands.command(name="lockedcommand", description="Say hello")
    @command_channel_lock()
    async def hello(self, ctx: commands.Context):
        await ctx.send("Hello")
        await asyncio.sleep(5)
        await ctx.send("World")

    async def ctx_menu(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        await interaction.response.send_message("hello...", ephemeral=True)

    async def ctx_menu_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        await interaction.response.send_message("error...", ephemeral=True)

    @app_commands.command(
        name="choose_dynamic_option",
        description="Choose one of the dynamically populated options.",
    )
    async def choose_dynamic_option(
        self, interaction: discord.Interaction, option: str
    ):
        # Respond to the user with the chosen option
        await interaction.response.send_message(f"You chose: {option}")

    # Override the autocomplete method to populate dynamic options
    @choose_dynamic_option.autocomplete("option")
    async def dynamic_option_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        # Get the dynamic options
        options = self.build_options()

        # Filter the options based on user input (`current`) to show matching options
        return [choice for choice in options if current.lower() in choice.name.lower()]


async def setup(bot):
    await bot.add_cog(Demo(bot))
