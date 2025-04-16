"""
COGNAME Cog

Description:
COGDESCRIPTION
"""

from discord.ext import commands


class COGNAME(commands.Cog, name="COGNAME", description="COGDESCRIPTION"):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def hello(self, ctx):
        """Responds with a hello message."""
        await ctx.send("Hello from <NAME>!")


def setup(bot):
    bot.add_cog(COGNAME(bot))
