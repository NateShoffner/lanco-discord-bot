"""
Counter Cog

Designates a channel as a counting channel. Users must count up from 1
in order. Sending the wrong number resets the count. The same user
cannot count twice in a row. Tracks the all-time high score.
"""

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from utils.command_utils import is_bot_owner_or_admin

from .models import CounterConfig


class Counter(
    LancoCog,
    name="Counter",
    description="Counting channel — count up together without making a mistake",
):
    def __init__(self, bot):
        super().__init__(bot)
        self.bot.database.create_tables([CounterConfig])

    @app_commands.command(
        name="counter", description="Set the counting channel for this server"
    )
    @app_commands.describe(channel="The channel to use for counting")
    @is_bot_owner_or_admin()
    async def set_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        config, created = CounterConfig.get_or_create(guild_id=interaction.guild.id)
        config.channel_id = channel.id
        config.current_count = 0
        config.last_user_id = None
        config.save()

        await interaction.response.send_message(
            f"✅ Counting channel set to {channel.mention}. Count starts at 1!",
            ephemeral=True,
        )
        await channel.send(
            "🔢 This channel is now the counting channel! Start counting from **1**."
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return

        try:
            config = CounterConfig.get(CounterConfig.guild_id == message.guild.id)
        except CounterConfig.DoesNotExist:
            return

        if config.channel_id != message.channel.id:
            return

        # Ignore if the same user sent the last count
        if config.last_user_id == message.author.id:
            await message.delete()
            try:
                await message.author.send(
                    f"❌ You can't count twice in a row in {message.channel.mention}! Let someone else go next."
                )
            except discord.Forbidden:
                pass
            return

        # Check if the message is the next number
        try:
            number = int(message.content.strip())
        except ValueError:
            return  # Not a number, ignore

        expected = config.current_count + 1

        if number == expected:
            # Correct count
            config.current_count = number
            config.last_user_id = message.author.id
            if number > config.high_score:
                config.high_score = number
            config.save()
            await message.add_reaction("✅")
        else:
            # Wrong number — reset
            ruined_by = message.author.mention
            reached = config.current_count
            high_score = config.high_score

            config.current_count = 0
            config.last_user_id = None
            config.save()

            await message.add_reaction("❌")
            await message.channel.send(
                f"😱 {ruined_by} ruined it at **{reached}**! The next number was **{expected}**.\n"
                f"🏆 High score: **{high_score}**\n"
                f"Start again from **1**."
            )


async def setup(bot):
    await bot.add_cog(Counter(bot))
