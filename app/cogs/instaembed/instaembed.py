import re

from cogs.common.embedfixcog import EmbedFixCog
from cogs.lancocog import UrlHandler
from discord import app_commands
from discord.ext import commands
from utils.command_utils import is_bot_owner_or_admin

from .models import InstaEmbedConfig


class InstaEmbed(EmbedFixCog, name="InstaEmbed", description="Instagram embed fix"):
    g = app_commands.Group(name="instaembed", description="InstaEmbed commands")

    insta_pattern = re.compile(r"https?://(?:www\.)?instagram\.com/p/[a-zA-Z0-9_-]+")

    def __init__(self, bot: commands.Bot):
        super().__init__(
            bot,
            "Instagram Embed Fix",
            [
                EmbedFixCog.PatternReplacement(
                    self.insta_pattern,
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

        bot.register_url_handler(
            UrlHandler(
                url_pattern=self.insta_pattern,
                cog=self,
                example_url="https://www.instagram.com/p/C69aOWwO4nM/",
            )
        )

    @g.command(name="toggle", description="Toggle Instagram embed fix for this server")
    @is_bot_owner_or_admin()
    async def toggle(self, interaction):
        await super().toggle(interaction)


async def setup(bot):
    await bot.add_cog(InstaEmbed(bot))
