from cogs.lancocog import LancoCog
from discord.ext import commands


class PeeCheck(LancoCog, name="PeeCheck", description="PeeCheck cog"):

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    @commands.command(name="peecheck", description="Mark your pee clarity")
    async def peecheck(self, ctx: commands.Context):
        msg = await ctx.send("Pee check! How clear is your pee?")
        colors_squares = ["⬜", "🟨", "🟧", "🟫", "🟥"]
        for color in colors_squares:
            await msg.add_reaction(color)

async def setup(bot):
    await bot.add_cog(PeeCheck(bot))
