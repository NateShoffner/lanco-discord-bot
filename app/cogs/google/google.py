import urllib.parse

from cogs.lancocog import LancoCog
from discord.ext import commands


class Google(LancoCog, name="Google", description="Google commands"):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    @commands.command(
        name="google",
        description="Google something",
        aliases=["g", "search", "bing", "askjeeves", "duckduckgo", "yahoo"],
    )
    async def google(self, ctx, *args):
        """Google something"""
        args = " ".join(args)
        encoded = urllib.parse.quote(args)
        url = f"https://www.google.com/search?q={encoded}"
        await ctx.send(f"<{url}>")


async def setup(bot):
    await bot.add_cog(Google(bot))
