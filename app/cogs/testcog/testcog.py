"""
testcog Cog

Description:
here is a desc
"""

from cogs.lancocog import LancoCog
from discord.ext import commands


class testcog(
    LancoCog,
    name="testcog",
    description="here is a desc",
):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.command()
    async def hello(self, ctx):
        """Responds with a hello message."""
        await ctx.send("Hello from testcog!")


async def setup(bot):
    await bot.add_cog(testcog(bot))
