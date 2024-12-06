import asyncio

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from utils.channel_lock import command_channel_lock


class Genshin(LancoCog, name="Genshin", description="Genshin cog"):

    blacklisted_words = ["genshin"]

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        if message.channel.id == 1146060051652546571:
            return

        if any(word in message.content.lower() for word in self.blacklisted_words):
            await message.add_reaction("⚠️")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author == self.bot.user:
            return

        if "*" in after.content and not any(
            word in after.content.lower() for word in self.blacklisted_words
        ):
            await after.remove_reaction("⚠️", self.bot.user)


async def setup(bot):
    await bot.add_cog(Genshin(bot))
