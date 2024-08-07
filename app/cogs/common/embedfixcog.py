import asyncio
import re

import discord
from cogs.lancocog import LancoCog
from db import BaseModel
from discord.ext import commands
from peewee import *


class EmbedFixConfigBase(BaseModel):
    guild_id = BigIntegerField(primary_key=True)
    enabled = BooleanField(default=False)


class EmbedFixCog(LancoCog):
    """Abstract class for fixing embeds to be extended by other cogs"""

    class PatternReplacement:
        """A pattern and its replacement"""

        def __init__(self, pattern: re.Pattern, original: str, replacement: str):
            """Initialize the pattern and its replacement

            Args:
                pattern (re.Pattern): The pattern to search for
                original (str): The original string to replace
                replacement (str): The replacement for the pattern
            """
            self.pattern = pattern
            self.original = original
            self.replacement = replacement

    def __init__(
        self,
        bot: commands.Bot,
        name: str,
        patterns: list[PatternReplacement],
        config_model: Model,
    ):
        """Initialize the cog

        Args:
            bot (commands.Bot): The bot
            name: (str) The name of the replacement (e.g. "Twitter")
            patterns (list[Pattern]): The patterns to search for and their replacements
            config_model (Model): The model to use for configuration
        """

        super().__init__(bot)
        self.name = name
        self.patterns = patterns
        self.config_model = config_model
        self.bot.database.create_tables([self.config_model])

    async def toggle(self, interaction: discord.Interaction):
        config, created = self.config_model.get_or_create(guild_id=interaction.guild.id)
        if created or not config.enabled:
            config.enabled = True
            config.save()
            await interaction.response.send_message(
                f"{self.name} enabled for this server"
            )
        else:
            config.enabled = False
            config.save()
            await interaction.response.send_message(
                f"{self.name} disabled for this server"
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        for pr in self.patterns:
            match = pr.pattern.search(message.content)
            if match:

                # wait a bit to see if discord will embed the link
                await asyncio.sleep(2.5)

                # re-fetch the message to get the latest content
                message = await message.channel.fetch_message(message.id)
                if message.embeds:
                    self.logger.info("Discord embedded the link, no need to fix it")
                    return

                embed_config = self.config_model.get_or_none(guild_id=message.guild.id)
                if not embed_config or not embed_config.enabled:
                    return

                await message.reply(match.group(0).replace(pr.original, pr.replacement))

                # suppress the original embed if we can
                if message.channel.permissions_for(message.guild.me).manage_messages:
                    await message.edit(suppress=True)
