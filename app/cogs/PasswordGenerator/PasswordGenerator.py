"""
Password generator (not for legit use)

Description:
Password generator (not for legit use)
"""

import secrets
import string

import discord
from cogs.lancocog import LancoCog
from discord.ext import commands


class PasswordGenerator(
    LancoCog,
    name="PasswordGenerator",
    description="Password generator (not for legit use)",
):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.command()
    async def password(self, ctx, length: int = 16):
        """Generates and returns a secure random password."""
        if length < 8 or length > 64:
            await ctx.send("🔒 Please choose a password length between 8 and 64.")
            return

        alphabet = string.ascii_letters + string.digits + string.punctuation
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        embed = discord.Embed(
            title="✨ Your Super-Secret Password! ✨",
            description=f"`{password}`",
            color=discord.Color.purple(),
        ).set_footer(text="Keep it safe and sound! Make sure nobody sees it! 🔐")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(PasswordGenerator(bot))
