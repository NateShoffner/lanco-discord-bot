import re

from cogs.common.embedfixcog import EmbedFixCog
from discord import app_commands
from discord.ext import commands
from utils.command_utils import is_bot_owner_or_admin

from .models import TikTokEmbedConfig


class TikTokEmbed(
    EmbedFixCog, name="TikTok Embed Fix", description="Fix TikTok embeds"
):
    g = app_commands.Group(name="tiktokembed", description="TikTokEmbed commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(
            bot,
            "TikTok Embed Fix",
            [
                EmbedFixCog.PatternReplacement(
                    re.compile(r"https?://(?:www\.)?tiktok\.com/\S+"),
                    "tiktok.com",
                    "vxtiktok.com",
                ),
            ],
            TikTokEmbedConfig,
        )

    @g.command(name="toggle", description="Toggle TikTok embed fix for this server")
    @is_bot_owner_or_admin()
    async def toggle(self, interaction):
        await super().toggle(interaction)


async def setup(bot):
    await bot.add_cog(TikTokEmbed(bot))
