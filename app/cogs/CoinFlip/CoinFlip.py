"""
CoinFlip Cog

Description:
Flip a coin
"""

import random

import discord
from cogs.lancocog import LancoCog
from discord.ext import commands


class CoinFlip(
    LancoCog,
    name="CoinFlip",
    description="Flip a coin",
):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.command(name="coinflip", description="Flip a coin")
    async def flip(self, ctx: commands.Context):
        """Flips a coin and returns the result."""
        result = "Heads" if random.choice([True, False]) else "Tails"
        await ctx.send(f"The coin landed on: **{result}**")


async def setup(bot):
    await bot.add_cog(CoinFlip(bot))
