import asyncio

from cogs.lancocog import LancoCog
from discord.ext import commands
from utils.channel_lock import command_channel_lock


class Demo(LancoCog, name="Demo", description="Demo cog"):

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info("Hello, world!")

    @commands.command(name="lockedcommand", description="Say hello")
    @command_channel_lock()
    async def hello(self, ctx: commands.Context):
        await ctx.send("Hello")
        await asyncio.sleep(5)
        await ctx.send("World")


async def setup(bot):
    await bot.add_cog(Demo(bot))
