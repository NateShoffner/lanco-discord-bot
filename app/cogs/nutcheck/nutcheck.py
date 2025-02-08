from datetime import datetime

import discord
from cogs.lancocog import LancoCog
from discord import Emoji
from discord.ext import commands
from PIL import Image


class NutCheck(LancoCog, name="NutCheck", description="NutCheck cog"):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    @commands.command(name="nutcheck", description="Mark yourself as having nutted")
    @commands.is_nsfw()
    async def nutcheck(self, ctx: commands.Context):
        now = datetime.now()

        if now.month != 11:
            await ctx.send("It is not November, you can nut all you want!")
            return

        def suffix(d):
            return {1: "st", 2: "nd", 3: "rd"}.get(d % 20, "th")

        embed = discord.Embed(
            title=f"No Nut November - November {now.day}{suffix(now.day)}",
            description="Have you nutted during NNN?",
            color=discord.Color.from_rgb(255, 255, 255),
        )
        msg = await ctx.send(embed=embed)
        emojis = ["🥜", "🚫"]
        for emoji in emojis:
            await msg.add_reaction(emoji)


async def setup(bot):
    await bot.add_cog(NutCheck(bot))
