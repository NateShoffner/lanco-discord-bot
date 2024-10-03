import re

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from utils.command_utils import is_bot_owner_or_admin
from utils.common import is_regex

from .models import AutoResponseConfig


class AutoResponse(LancoCog, name="AutoResponse", description="AutoResponse cog"):
    g = app_commands.Group(name="autoresponse", description="AutoResponse commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot.database.create_tables([AutoResponseConfig])

    @g.command(name="add", description="Set an auto-response")
    @is_bot_owner_or_admin()
    async def set_auto_response(
        self, interaction: discord.Interaction, phrase: str, response: str
    ):
        config, created = AutoResponseConfig.get_or_create(
            guild_id=interaction.guild.id, phrase=phrase, response=response
        )
        config.save()
        await interaction.response.send_message(
            "Auto-response phrase set", ephemeral=True
        )

    @g.command(
        name="addregex",
        description="Set an auto-response response with a regex pattern",
    )
    @is_bot_owner_or_admin()
    async def set_auto_response_regex(
        self, interaction: discord.Interaction, pattern: str, response: str
    ):
        if not is_regex(pattern):
            await interaction.response.send_message(
                "Please provide a valid regex pattern", ephemeral=True
            )
            return

        config, created = AutoResponseConfig.get_or_create(
            guild_id=interaction.guild.id,
            phrase=pattern,
            response=response,
            is_regex=True,
        )
        config.save()
        await interaction.response.send_message(
            "Auto-response phrase set", ephemeral=True
        )

    @g.command(name="remove", description="Remove the auto-response")
    @is_bot_owner_or_admin()
    async def remove_auto_response(
        self, interaction: discord.Interaction, phrase: str, response: str = None
    ):
        if response:
            config = AutoResponseConfig.get_or_none(
                guild_id=interaction.guild.id, phrase=phrase, response=response
            )
        else:
            config = AutoResponseConfig.get_or_none(
                guild_id=interaction.guild.id, phrase=phrase
            )

        if not config:
            await interaction.response.send_message(
                "Auto-response phrase not found", ephemeral=True
            )
            return

        config.delete_instance()
        await interaction.response.send_message(
            "Auto-response phrase removed", ephemeral=True
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        config = AutoResponseConfig.get_or_none(guild_id=message.guild.id)
        if not config:
            return

        if config.is_regex:
            if re.findall(config.phrase, message.content):
                await message.reply(config.response)
        else:
            message_words = message.content.split()
            if config.phrase in message_words:
                await message.reply(config.response)


async def setup(bot):
    await bot.add_cog(AutoResponse(bot))
