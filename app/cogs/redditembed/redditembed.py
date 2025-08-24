import re

from cogs.common.embedfixcog import EmbedFixCog
from cogs.lancocog import UrlHandler
from discord import app_commands
from discord.ext import commands
from utils.command_utils import is_bot_owner_or_admin

from .models import RedditEmbedConfig


class RedditEmbed(EmbedFixCog, name="RedditEmbed", description="RedditEmbed cog"):
    g = app_commands.Group(name="redditembed", description="RedditEmbed commands")

    reddit_pattern = re.compile(r"https?://(?:www\.)?reddit\.com/\S+")

    def __init__(self, bot: commands.Bot):
        super().__init__(
            bot,
            "Reddit Embed Fix",
            [
                EmbedFixCog.PatternReplacement(
                    self.reddit_pattern,
                    "www.reddit.com",
                    "rxddit.com",
                )
            ],
            RedditEmbedConfig,
        )

        bot.register_url_handler(
            UrlHandler(
                url_pattern=self.reddit_pattern,
                cog=self,
                example_url="https://www.reddit.com/r/AskReddit/comments/cq1q2/help_reddit_turned_spanish_and_i_cannot_undo_it/",
            )
        )

    @g.command(name="toggle", description="Toggle Reddit embed fix for this server")
    @is_bot_owner_or_admin()
    async def toggle(self, interaction):
        await super().toggle(interaction)


async def setup(bot):
    await bot.add_cog(RedditEmbed(bot))
