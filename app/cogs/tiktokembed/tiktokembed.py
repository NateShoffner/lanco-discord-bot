import re
import discord
from discord.ext import commands
from discord import app_commands
from .models import TikTokEmbedConfig

from cogs.lancocog import LancoCog


class TikTokEmbed(LancoCog):
    tiktok_embed_group = app_commands.Group(
        name="tiktokembed", description="TikTokEmbed commands"
    )

    tiktok_url_pattern = re.compile(r"https?://(?:www\.)?tiktok\.com/\S+")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot = bot
        self.bot.database.create_tables([TikTokEmbedConfig])

    @tiktok_embed_group.command(name="enable", description="Enable TikTokEmbed")
    @commands.has_permissions(administrator=True)
    @commands.is_owner()
    async def enable(self, interaction: discord.Interaction):
        tiktoktfix_config, created = TikTokEmbedConfig.get_or_create(
            guild_id=interaction.guild.id
        )
        tiktoktfix_config.enabled = True
        tiktoktfix_config.save()

        await interaction.response.send_message("TikTokEmbed enabled", ephemeral=True)

    @tiktok_embed_group.command(name="disable", description="Disable TikTokEmbed")
    @commands.has_permissions(administrator=True)
    @commands.is_owner()
    async def disable(self, interaction: discord.Interaction):
        tiktoktfix_config, created = TikTokEmbedConfig.get_or_create(
            guild_id=interaction.guild.id
        )
        tiktoktfix_config.enabled = False
        tiktoktfix_config.save()

        await interaction.response.send_message("TikTokEmbed disabled", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        match = self.tiktok_url_pattern.search(message.content)
        if match:
            tiktoktfix_config = TikTokEmbedConfig.get_or_none(guild_id=message.guild.id)
            if not tiktoktfix_config or not tiktoktfix_config.enabled:
                return

            fixed = match.group(0).replace("tiktok.com", "vxtiktok.com")
            await message.reply(fixed)

            # suppress the original embed if we can
            if message.channel.permissions_for(message.guild.me).manage_messages:
                await message.edit(suppress=True)


async def setup(bot):
    await bot.add_cog(TikTokEmbed(bot))
