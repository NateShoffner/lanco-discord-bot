import re
from discord.ext import commands
from discord import app_commands
from .models import InstaEmbedConfig
from cogs.common.embedfixcog import EmbedFixCog


class InstaEmbed(EmbedFixCog):
    g = app_commands.Group(name="instaembed", description="InstaEmbed commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(
            bot,
            "Instagram Embed Fix",
            [
                EmbedFixCog.PatternReplacement(
                    re.compile(r"https?://(?:www\.)?instagram\.com/p/\S+"),
                    "instagram.com",
                    "ddinstagram.com",
                ),
                EmbedFixCog.PatternReplacement(
                    re.compile(r"https?://(?:www\.)?instagram\.com/reel/\S+"),
                    "instagram.com",
                    "ddinstagram.com",
                ),
            ],
            InstaEmbedConfig,
        )

    @g.command(name="toggle", description="Toggle Instagram embed fix for this server")
    @commands.check_any(
        commands.has_permissions(administrator=True), commands.is_owner()
    )
    async def toggle(self, interaction):
        await super().toggle(interaction)


async def setup(bot):
    await bot.add_cog(InstaEmbed(bot))
