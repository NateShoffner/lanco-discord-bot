import re

from cogs.common.embedfixcog import EmbedFixCog
from discord import app_commands
from discord.ext import commands
from utils.command_utils import is_bot_owner_or_admin

from app.cogs.lancocog import UrlHandler

from .models import TikTokEmbedConfig


class TikTokEmbed(
    EmbedFixCog, name="TikTok Embed Fix", description="Fix TikTok embeds"
):
    g = app_commands.Group(name="tiktokembed", description="TikTokEmbed commands")

    tiktok_pattern = re.compile(r"https?://(?:www\.)?tiktok\.com/\S+")

    def __init__(self, bot: commands.Bot):
        super().__init__(
            bot,
            "TikTok Embed Fix",
            [
                EmbedFixCog.PatternReplacement(
                    self.tiktok_pattern,
                    "tiktok.com",
                    "vxtiktok.com",
                ),
            ],
            TikTokEmbedConfig,
        )

        bot.register_url_handler(
            UrlHandler(
                url_pattern=self.tiktok_pattern,
                cog=self,
                example_url="https://www.tiktok.com/@de_cs2/video/7369644813400034593",
            )
        )

    @g.command(name="toggle", description="Toggle TikTok embed fix for this server")
    @is_bot_owner_or_admin()
    async def toggle(self, interaction):
        await super().toggle(interaction)


async def setup(bot):
    await bot.add_cog(TikTokEmbed(bot))
