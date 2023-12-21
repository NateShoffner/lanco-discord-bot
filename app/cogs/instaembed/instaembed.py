import re
import discord
from discord.ext import commands
from discord import app_commands
from .models import InstaEmbedConfig

from cogs.lancocog import LancoCog


class InstaEmbed(LancoCog):
    insta_embed_group = app_commands.Group(
        name="instaembed", description="InstaEmbed commands"
    )

    instagram_url_pattern = re.compile(r"https?://(?:www\.)?instagram\.com/p/\S+")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot = bot
        self.bot.database.create_tables([InstaEmbedConfig])

    @insta_embed_group.command(name="enable", description="Enable InstaEmbed")
    @commands.has_permissions(administrator=True)
    @commands.is_owner()
    async def enable(self, interaction: discord.Interaction):
        insta_embed_config, created = InstaEmbedConfig.get_or_create(
            guild_id=interaction.guild.id
        )
        insta_embed_config.enabled = True
        insta_embed_config.save()

        await interaction.response.send_message("InstaEmbed enabled", ephemeral=True)

    @insta_embed_group.command(name="disable", description="Disable InstaEmbed")
    @commands.has_permissions(administrator=True)
    @commands.is_owner()
    async def disable(self, interaction: discord.Interaction):
        insta_embed_config, created = InstaEmbedConfig.get_or_create(
            guild_id=interaction.guild.id
        )
        insta_embed_config.enabled = False
        insta_embed_config.save()

        await interaction.response.send_message("InstaEmbed disabled", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        match = self.instagram_url_pattern.search(message.content)
        if match:
            insta_embed_config = InstaEmbedConfig.get_or_none(guild_id=message.guild.id)
            if not insta_embed_config or not insta_embed_config.enabled:
                return

            fixed = match.group(0).replace("instagram.com", "ddinstagram.com")
            await message.reply(fixed)

            # suppress the original embed if we can
            if message.channel.permissions_for(message.guild.me).manage_messages:
                await message.edit(suppress=True)


async def setup(bot):
    await bot.add_cog(InstaEmbed(bot))
