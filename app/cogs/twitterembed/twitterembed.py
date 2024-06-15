import re

from cogs.common.embedfixcog import EmbedFixCog
from cogs.lancocog import UrlHandler
from discord import app_commands
from main import LancoBot
from utils.command_utils import is_bot_owner_or_admin

from .models import TwitterEmbedConfig


class TwitterEmbed(
    EmbedFixCog, name="Twitter/X Embed Fix", description="Fix Twitter/X embeds"
):
    g = app_commands.Group(name="twitterembed", description="TwitterEmbed commands")

    def __init__(self, bot: LancoBot):
        twitter_pattern = re.compile(
            r"https?://(?:www\.)?twitter\.com/([a-zA-Z0-9_]+)/status/([0-9]+)\S+"
        )

        x_pattern = re.compile(
            r"https?://(?:www\.)?x\.com/([a-zA-Z0-9]+)/status/([0-9]+)\S+"
        )

        super().__init__(
            bot,
            "Twitter/X Embed Fix",
            [
                EmbedFixCog.PatternReplacement(
                    twitter_pattern,
                    "twitter.com",
                    "fxtwitter.com",
                ),
                EmbedFixCog.PatternReplacement(
                    x_pattern,
                    "x.com",
                    "fxtwitter.com",
                ),
            ],
            TwitterEmbedConfig,
        )

        bot.register_url_handler(
            UrlHandler(
                url_pattern=twitter_pattern,
                cog=self,
                example_url="https://twitter.com/jack/status/20",
            )
        )
        bot.register_url_handler(
            UrlHandler(
                url_pattern=x_pattern,
                cog=self,
                example_url="https://x.com/jack/status/20",
            )
        )

    @g.command(name="toggle", description="Toggle Twitter/X embed fix for this server")
    @is_bot_owner_or_admin()
    async def toggle(self, interaction):
        await super().toggle(interaction)


async def setup(bot):
    await bot.add_cog(TwitterEmbed(bot))
