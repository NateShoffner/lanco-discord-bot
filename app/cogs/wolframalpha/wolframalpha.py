import datetime
import os

import wolframalpha
from cogs.lancocog import LancoCog
from discord.ext import commands, tasks


class WolframAlpha(
    LancoCog, name="WolframAlpha", description="Queries Wolfram Alpha for information"
):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.client = wolframalpha.Client(os.getenv("WOLFRAM_ALPHA_API_KEY"))

    @commands.command(name="calc", description="Query Wolfram Alpha")
    async def calc(self, ctx: commands.Context, *, query: str):
        if not query:
            await ctx.message.reply("Please provide a query")
            return

        res = self.client.query(query)
        result = list(res.results)[-1]

        plain_text = result.text

        if result is not None:
            await ctx.message.reply(f"{plain_text}")
        else:
            await ctx.message.reply("No results found")


async def setup(bot):
    await bot.add_cog(WolframAlpha(bot))
