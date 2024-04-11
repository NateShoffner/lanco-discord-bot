import re

from cogs.common.embedfixcog import EmbedFixCog
from discord import app_commands
from discord.ext import commands

from .models import TwitterEmbedConfig


class TwitterEmbed(
    EmbedFixCog, name="Twitter/X Embed Fix", description="Fix Twitter/X embeds"
):
    g = app_commands.Group(name="twitterembed", description="TwitterEmbed commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(
            bot,
            "Twitter/X Embed Fix",
            [
                EmbedFixCog.PatternReplacement(
                    re.compile(
                        r"https?://(?:www\.)?twitter\.com/([a-zA-Z0-9_]+)/status/([0-9]+)\S+"
                    ),
                    "twitter.com",
                    "fxtwitter.com",
                ),
                EmbedFixCog.PatternReplacement(
                    re.compile(
                        r"https?://(?:www\.)?x\.com/([a-zA-Z0-9]+)/status/([0-9]+)\S+"
                    ),
                    "x.com",
                    "fxtwitter.com",
                ),
            ],
            TwitterEmbedConfig,
        )

    @g.command(name="toggle", description="Toggle Twitter/X embed fix for this server")
    @commands.check_any(
        commands.has_permissions(administrator=True), commands.is_owner()
    )
    async def toggle(self, interaction):
        await super().toggle(interaction)


async def setup(bot):
    await bot.add_cog(TwitterEmbed(bot))
