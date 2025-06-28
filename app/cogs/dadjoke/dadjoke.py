"""
dadjoke Cog

Description:
dadjoke cog
"""

import asyncio
import re

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from utils.command_utils import is_bot_owner_or_admin

from .models import DadJokeConfig


class dadjoke(
    LancoCog,
    name="dadjoke",
    description="dadjoke cog",
):
    g = app_commands.Group(name="dadjoke", description="Dad joke commands")

    def __init__(self, bot):
        super().__init__(bot)
        self.bot.database.create_tables([DadJokeConfig])

    @g.command(name="toggle", description="Toggle dad jokes")
    @is_bot_owner_or_admin()
    async def toggle(self, interaction: discord.Interaction):
        config, created = DadJokeConfig.get_or_create(channel_id=interaction.channel.id)
        if created:
            config.enabled = True
            config.save()
            await interaction.response.send_message(
                "Dad jokes enabled. Use `/dadjoke toggle` to disable."
            )
        else:
            config.delete_instance()
            await interaction.response.send_message(
                "Dad jokes disabled. Use `/dadjoke toggle` to enable."
            )

    async def change_name(self, member: discord.Member, new_name: str):
        try:
            old_nick = member.nick or member.name

            self.logger.info(
                f"Changing nickname for {member.name} to {new_name} in {member.guild.name}"
            )

            await member.edit(nick=new_name)

            # Schedule nickname reset
            async def reset_nick():
                await asyncio.sleep(10)
                try:
                    await member.edit(nick=old_nick)
                except Exception as e:
                    print(f"Failed to reset nickname: {e}")

            asyncio.create_task(reset_nick())
        except discord.Forbidden:
            self.logger.error(
                f"Failed to change nickname for {member.name} in {member.guild.name}. "
                "Check if the bot has permission to manage nicknames."
            )
        except discord.HTTPException as e:
            self.logger.error(
                f"Failed to change nickname for {member.name} in {member.guild.name}: {e}"
            )

    def is_valid_discord_name(self, name: str) -> bool:
        """Check if the name is a valid Discord username."""
        if len(name) > 32 or len(name) < 2:
            return False
        if not re.match(r"^[\w-]+$", name):
            return False
        return True

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        if not DadJokeConfig.get_or_none(channel_id=message.channel.id, enabled=True):
            return

        pattern = re.compile(r"\bI['’]?m ([^\n\r]+)", re.IGNORECASE)

        match = pattern.search(message.content)
        if not match:
            return

        new_name = match.group(1).strip()

        if not self.is_valid_discord_name(new_name):
            return

        member = message.author

        await self.change_name(member, new_name)

        bot_name = message.guild.me.display_name
        response = f"Hi, {new_name}, I'm {bot_name}!"
        await message.channel.send(response)


async def setup(bot):
    await bot.add_cog(dadjoke(bot))
