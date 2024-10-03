import asyncio

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from utils.channel_lock import command_channel_lock


class Demo(LancoCog, name="Demo", description="Demo cog"):
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


async def setup(bot):
    await bot.add_cog(Demo(bot))
