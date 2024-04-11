import re

from cogs.common.embedfixcog import EmbedFixCog
from discord import app_commands
from discord.ext import commands

from .models import RedditEmbedConfig


class RedditEmbed(EmbedFixCog):
    g = app_commands.Group(name="redditembed", description="RedditEmbed commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(
            bot,
            "Reddit Embed Fix",
            [
                EmbedFixCog.PatternReplacement(
                    re.compile(r"https?://(?:www\.)?reddit\.com/\S+"),
                    "www.reddit.com",
                    "rxddit.com",
                )
            ],
            RedditEmbedConfig,
        )

    @g.command(name="toggle", description="Toggle Reddit embed fix for this server")
    @commands.check_any(
        commands.has_permissions(administrator=True), commands.is_owner()
    )
    async def toggle(self, interaction):
        await super().toggle(interaction)


async def setup(bot):
    await bot.add_cog(RedditEmbed(bot))
