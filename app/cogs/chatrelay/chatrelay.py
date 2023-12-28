import re
import discord
from discord.ext import commands
from discord import app_commands
from cogs.lancocog import LancoCog


class ChatRelay(LancoCog):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot = bot
        self.recepient_channel_id = None

    @commands.command(name="relay", description="Set the channel to relay messages to")
    @commands.is_owner()
    async def set_recepient_channel(self, ctx: commands.Context, channel_id: int):
        self.recepient_channel_id = channel_id
        channel = self.bot.get_channel(self.recepient_channel_id)
        if not channel:
            await ctx.send("Channel not found")
            return
        await ctx.send(f"Recepient channel set to {channel.mention}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not isinstance(message.channel, discord.DMChannel):
            return
        if not self.recepient_channel_id:
            return

        if message.content.startswith(self.bot.command_prefix):
            return

        self.logger.info(
            f"Message received from {message.author.name}: {message.content}"
        )

        channel = self.bot.get_channel(self.recepient_channel_id)
        await channel.send(f"{message.content}")


async def setup(bot):
    await bot.add_cog(ChatRelay(bot))
