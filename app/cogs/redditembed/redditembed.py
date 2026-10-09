import re

from cogs.common.embedfixcog import EmbedFixCog
from cogs.lancocog import UrlHandler
from discord import app_commands
from discord.ext import commands
from utils.command_utils import is_bot_owner_or_admin

from .models import RedditEmbedConfig


class RedditEmbed(
    EmbedFixCog, name="RedditEmbed", description="Fix Reddit embed previews in Discord"
):
    g = app_commands.Group(
        name="redditembed", description="RedditEmbed commands", guild_only=True
    )

    reddit_pattern = re.compile(r"https?://(?:www\.)?reddit\.com/\S+")

    def __init__(self, bot: commands.Bot):
        super().__init__(
            bot,
            "Reddit Embed Fix",
            [
                # rxddit.com, the vxReddit author's own instance, was the default
                # until Reddit started blocking it; it now answers every request
                # with an error card. vxreddit.com is the same project on
                # unblocked hosting. The replacement is "reddit.com" rather than
                # "www.reddit.com" so bare-domain links get rewritten too; the
                # fixers serve the resulting www.<fixer> host just the same.
                EmbedFixCog.Handler(
                    "vxreddit",
                    "VxReddit",
                    "Uses vxreddit.com",
                    [
                        EmbedFixCog.PatternReplacement(
                            self.reddit_pattern, "reddit.com", "vxreddit.com"
                        ),
                    ],
                ),
                EmbedFixCog.Handler(
                    "redditez",
                    "RedditEZ",
                    "Uses redditez.com (EmbedEZ)",
                    [
                        EmbedFixCog.PatternReplacement(
                            self.reddit_pattern, "reddit.com", "redditez.com"
                        ),
                    ],
                ),
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

    @g.command(
        name="handler",
        description="Switch the Reddit embed handler for this server",
    )
    @is_bot_owner_or_admin()
    async def handler(self, interaction):
        await self._show_handler_select(interaction)


async def setup(bot):
    await bot.add_cog(RedditEmbed(bot))
