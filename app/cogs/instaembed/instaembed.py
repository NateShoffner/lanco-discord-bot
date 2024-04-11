import re

from cogs.common.embedfixcog import EmbedFixCog
from discord import app_commands
from discord.ext import commands

from .models import InstaEmbedConfig


class InstaEmbed(EmbedFixCog):
    g = app_commands.Group(name="instaembed", description="InstaEmbed commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(
            bot,
            "Instagram Embed Fix",
            [
                EmbedFixCog.PatternReplacement(
                    re.compile(r"https?://(?:www\.)?instagram\.com/p/[a-zA-Z0-9_-]+"),
                    "instagram.com",
                    "ddinstagram.com",
                ),
                EmbedFixCog.PatternReplacement(
                    re.compile(
                        r"https?://(?:www\.)?instagram\.com/reel/[a-zA-Z0-9_-]+"
                    ),
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
