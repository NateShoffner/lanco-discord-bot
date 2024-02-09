import re
import discord
from discord.ext import commands
from discord import app_commands
from .models import TwitterEmbedConfig

from cogs.lancocog import LancoCog


class TwitterEmbed(LancoCog):
    twitter_embed_group = app_commands.Group(
        name="twitterembed", description="TwitterEmbed commands"
    )

    twitter_url_pattern = re.compile(r"https?://(?:www\.)?twitter\.com/\S+")
    x_url_pattern = re.compile(r"https?://(?:www\.)?x\.com/\S+")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot = bot
        self.bot.database.create_tables([TwitterEmbedConfig])

    @twitter_embed_group.command(name="enable", description="Enable TwitterEmbed")
    @commands.has_permissions(administrator=True)
    @commands.is_owner()
    async def enable(self, interaction: discord.Interaction):
        twitterembed_config, created = TwitterEmbedConfig.get_or_create(
            guild_id=interaction.guild.id
        )
        twitterembed_config.enabled = True
        twitterembed_config.save()

        await interaction.response.send_message("TwitterEmbed enabled")

    @twitter_embed_group.command(name="disable", description="Disable TwitterEmbed")
    @commands.has_permissions(administrator=True)
    @commands.is_owner()
    async def disable(self, interaction: discord.Interaction):
        twitterembed_config, created = TwitterEmbedConfig.get_or_create(
            guild_id=interaction.guild.id
        )
        twitterembed_config.enabled = False
        twitterembed_config.save()

        await interaction.response.send_message("TwitterEmbed disabled")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        twitter_match = self.twitter_url_pattern.search(message.content)
        x_match = self.x_url_pattern.search(message.content)
        if twitter_match or x_match:
            twitterembed_config = TwitterEmbedConfig.get_or_none(
                guild_id=message.guild.id
            )
            if not twitterembed_config or not twitterembed_config.enabled:
                return

            if twitter_match:
                fixed = twitter_match.group(0).replace("twitter.com", "fxtwitter.com")
            if x_match:
                fixed = x_match.group(0).replace("x.com", "fxtwitter.com")
            await message.reply(fixed)

            # suppress the original embed if we can
            if message.channel.permissions_for(message.guild.me).manage_messages:
                await message.edit(suppress=True)


async def setup(bot):
    await bot.add_cog(TwitterEmbed(bot))
