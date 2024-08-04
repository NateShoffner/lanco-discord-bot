import json
import os
import random

from cogs.lancocog import LancoCog
from discord.ext import commands


class FortuneCookie(LancoCog, name="FortuneCookie", description="FortuneCookie cog"):

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    async def cog_load(self):
        FORTUNES_FILE = os.path.join(self.get_cog_directory(), "fortunes.json")
        with open(FORTUNES_FILE, "r") as f:
            self.fortunes = json.load(f)

    @commands.command(
        name="fortunecookie",
        description="Get a fortune cookie",
        aliases=["fortune", "cookie"],
    )
    async def fortunecookie(self, ctx: commands.Context):
        fortune = random.choice(self.fortunes)
        await ctx.send(f"🥠 {fortune}")


async def setup(bot):
    await bot.add_cog(FortuneCookie(bot))
