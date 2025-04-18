"""
COGNAME Cog

Description:
COGDESCRIPTION
"""

from cogs.lancocog import LancoCog
from discord.ext import commands


class COGNAME(
    LancoCog,
    name="COGNAME",
    description="COGDESCRIPTION",
):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.command()
    async def hello(self, ctx):
        """Responds with a hello message."""
        await ctx.send("Hello from COGNAME!")


def setup(bot):
    bot.add_cog(COGNAME(bot))
