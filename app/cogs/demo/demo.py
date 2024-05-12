from cogs.lancocog import LancoCog
from discord.ext import commands


class Demo(LancoCog, name="Demo", description="Demo cog"):

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info("Hello, world!")


async def setup(bot):
    await bot.add_cog(Demo(bot))
