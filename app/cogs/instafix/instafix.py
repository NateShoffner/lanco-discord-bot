import re
import discord
from discord.ext import commands
from discord import app_commands
from .models import InstaFixConfig

from cogs.lancocog import LancoCog


class InstaFix(LancoCog):
    instafix_group = app_commands.Group(
        name="instafix", description="InstaFix commands"
    )

    instagram_url_pattern = re.compile(r"https?://(?:www\.)?instagram\.com/\S+")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.database.create_tables([InstaFixConfig])

    @commands.Cog.listener()
    async def on_ready(self):
        print("InstaFix cog loaded")
        await super().on_ready()

    @instafix_group.command(name="enable", description="Enable InstaFix")
    @commands.has_permissions(administrator=True)
    @commands.is_owner()
    async def enable(self, interaction: discord.Interaction):
        instafix_config, created = InstaFixConfig.get_or_create(
            guild_id=interaction.guild.id
        )
        instafix_config.enabled = True
        instafix_config.save()

        await interaction.response.send_message("InstaFix enabled", ephemeral=True)

    @instafix_group.command(name="disable", description="Disable InstaFix")
    @commands.has_permissions(administrator=True)
    @commands.is_owner()
    async def disable(self, interaction: discord.Interaction):
        instafix_config, created = InstaFixConfig.get_or_create(
            guild_id=interaction.guild.id
        )
        instafix_config.enabled = False
        instafix_config.save()

        await interaction.response.send_message("InstaFix disabled", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        match = self.instagram_url_pattern.search(message.content)
        if match:
            instafix_config = InstaFixConfig.get_or_none(guild_id=message.guild.id)
            if not instafix_config or not instafix_config.enabled:
                return

            fixed = match.group(0).replace("instagram.com", "ddinstagram.com")
            await message.reply(fixed)


async def setup(bot):
    await bot.add_cog(InstaFix(bot))
