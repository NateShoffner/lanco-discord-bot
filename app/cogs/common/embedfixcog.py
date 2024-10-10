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
        skip_if_handled_by_discord: bool = False,
        wait_time: float = 2.5,
    ):
        """Initialize the cog

        Args:
            bot (commands.Bot): The bot
            name: (str) The name of the replacement (e.g. "Twitter")
            patterns (list[Pattern]): The patterns to search for and their replacements
            config_model (Model): The model to use for configuration
            skip_if_handled_by_discord (bool): Whether to skip if discord embeds the link
            wait_time (float): The time to wait before fixing the embed
        """

        super().__init__(bot)
        self.name = name
        self.patterns = patterns
        self.config_model = config_model
        self.skip_if_handled_by_discord = skip_if_handled_by_discord
        self.wait_time = wait_time
        self.bot.database.create_tables([self.config_model])
        self.fixed_messages = {} # message_id -> fixed_message_id

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
                original_url = match.group(0)
                fixed_url = original_url.replace(pr.original, pr.replacement)

                self.logger.info(
                    f"Found URL to be handled by {self.name}: {original_url} -> {fixed_url} - waiting {self.wait_time}s"
                )

                # wait a bit to see if discord will embed the link
                await asyncio.sleep(self.wait_time)

                # re-fetch the message to get the latest content
                message = await message.channel.fetch_message(message.id)
                if message.embeds and self.skip_if_handled_by_discord:
                    self.logger.info("Discord embedded the link, no need to fix it")
                    return

                embed_config = self.config_model.get_or_none(guild_id=message.guild.id)
                if not embed_config or not embed_config.enabled:
                    self.logger.info("Embed fix not enabled for this server")
                    return

                fixed_msg = await message.reply(fixed_url)
                self.fixed_messages[message.id] = fixed_msg.id

                # suppress the original embed if we can
                if message.channel.permissions_for(message.guild.me).manage_messages:
                    await message.edit(suppress=True)


    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        fixed_message_id = self.fixed_messages.get(message.id)
        if fixed_message_id:
            fixed_message = await message.channel.fetch_message(fixed_message_id)
            await fixed_message.delete()
        