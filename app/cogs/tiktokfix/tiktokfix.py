import re
import discord
from discord.ext import commands
from discord import app_commands
from .models import TikTokFixConfig

from cogs.lancocog import LancoCog


class TikTokFix(LancoCog):
    tiktokfix_group = app_commands.Group(
        name="tiktokfix", description="TikTokFix commands"
    )

    tiktok_url_pattern = re.compile(r"https?://(?:www\.)?tiktok\.com/\S+")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.database.create_tables([TikTokFixConfig])

    @commands.Cog.listener()
    async def on_ready(self):
        print("TikTokFix cog loaded")
        await super().on_ready()

    @tiktokfix_group.command(name="enable", description="Enable TikTokFix")
    @commands.has_permissions(administrator=True)
    @commands.is_owner()
    async def enable(self, interaction: discord.Interaction):
        tiktoktfix_config, created = TikTokFixConfig.get_or_create(
            guild_id=interaction.guild.id
        )
        tiktoktfix_config.enabled = True
        tiktoktfix_config.save()

        await interaction.response.send_message("TikTokFix enabled", ephemeral=True)

    @tiktokfix_group.command(name="disable", description="Disable TikTokFix")
    @commands.has_permissions(administrator=True)
    @commands.is_owner()
    async def disable(self, interaction: discord.Interaction):
        tiktoktfix_config, created = TikTokFixConfig.get_or_create(
            guild_id=interaction.guild.id
        )
        tiktoktfix_config.enabled = False
        tiktoktfix_config.save()

        await interaction.response.send_message("TikTokFix disabled", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        match = self.tiktok_url_pattern.search(message.content)
        if match:
            tiktoktfix_config = TikTokFixConfig.get_or_none(guild_id=message.guild.id)
            if not tiktoktfix_config or not tiktoktfix_config.enabled:
                return

            fixed = match.group(0).replace("tiktok.com", "vxtiktok.com")
            await message.reply(fixed)


async def setup(bot):
    await bot.add_cog(TikTokFix(bot))