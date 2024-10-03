import re

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from utils.command_utils import is_bot_owner_or_admin
from utils.common import is_emoji, is_regex

from .models import AutoReactConfig


class AutoReact(LancoCog, name="AutoReact", description="AutoReact cog"):
    g = app_commands.Group(name="autoreact", description="AutoReact commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot.database.create_tables([AutoReactConfig])

    @g.command(name="add", description="Set an auto-react response")
    @is_bot_owner_or_admin()
    async def set_auto_react(
        self, interaction: discord.Interaction, phrase: str, reaction: str
    ):
        if not is_emoji(reaction):
            await interaction.response.send_message(
                "Please provide a valid emoji", ephemeral=True
            )
            return

        config, created = AutoReactConfig.get_or_create(
            guild_id=interaction.guild.id, phrase=phrase, emoji=reaction
        )
        config.save()
        await interaction.response.send_message("Auto-react phrase set", ephemeral=True)

    @g.command(
        name="addregex", description="Set an auto-react response with a regex pattern"
    )
    @is_bot_owner_or_admin()
    async def set_auto_react_regex(
        self, interaction: discord.Interaction, pattern: str, reaction: str
    ):
        if not is_emoji(reaction):
            await interaction.response.send_message(
                "Please provide a valid emoji", ephemeral=True
            )
            return

        if not is_regex(pattern):
            await interaction.response.send_message(
                "Please provide a valid regex pattern", ephemeral=True
            )
            return

        config, created = AutoReactConfig.get_or_create(
            guild_id=interaction.guild.id, phrase=pattern, emoji=reaction, is_regex=True
        )
        config.save()
        await interaction.response.send_message("Auto-react phrase set", ephemeral=True)

    @g.command(name="remove", description="Remove the auto-react response")
    @is_bot_owner_or_admin()
    async def remove_auto_react(
        self, interaction: discord.Interaction, phrase: str, reaction: str = None
    ):
        if reaction:
            config = AutoReactConfig.get_or_none(
                guild_id=interaction.guild.id, phrase=phrase, emoji=reaction
            )
        else:
            config = AutoReactConfig.get_or_none(
                guild_id=interaction.guild.id, phrase=phrase
            )

        if not config:
            await interaction.response.send_message(
                "Auto-react phrase not found", ephemeral=True
            )
            return

        config.delete_instance()
        await interaction.response.send_message(
            "Auto-react phrase removed", ephemeral=True
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        config = AutoReactConfig.get_or_none(guild_id=message.guild.id)
        if not config:
            return

        if config.is_regex:
            if re.findall(config.phrase, message.content):
                await message.add_reaction(config.emoji)
        else:
            message_words = message.content.split()
            if config.phrase in message_words:
                await message.add_reaction(config.emoji)


async def setup(bot):
    await bot.add_cog(AutoReact(bot))
