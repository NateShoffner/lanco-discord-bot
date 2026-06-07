from cogs.lancocog import LancoCog
from discord.ext import commands


class COGNAME(LancoCog, name="COGNAME", description="COGDESCRIPTION"):
    def __init__(self, bot):
        super().__init__(bot)

    async def cog_load(self):
        await super().cog_load()


async def setup(bot):
    await bot.add_cog(COGNAME(bot))
