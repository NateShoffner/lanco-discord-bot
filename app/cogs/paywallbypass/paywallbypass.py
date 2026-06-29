import re

import discord
from cogs.common.embedfixcog import EmbedFixCog
from discord import app_commands
from discord.ext import commands
from utils.command_utils import is_bot_owner_or_admin

from .models import PaywallBypassConfig

_LANCASTERONLINE_PATTERN = re.compile(r"https?://(?:www\.)?lancasteronline\.com/\S+")

_HANDLERS = [
    EmbedFixCog.Handler(
        "removepaywall",
        "Remove Paywall",
        "Uses removepaywall.com",
        [EmbedFixCog.PatternReplacement(_LANCASTERONLINE_PATTERN, "", "")],
        service_url="https://removepaywall.com/",
    ),
    EmbedFixCog.Handler(
        "archiveph",
        "Archive.ph",
        "Uses archive.ph",
        [EmbedFixCog.PatternReplacement(_LANCASTERONLINE_PATTERN, "", "")],
        service_url="https://archive.ph/",
    ),
    EmbedFixCog.Handler(
        "wayback",
        "Wayback Machine",
        "Uses web.archive.org",
        [EmbedFixCog.PatternReplacement(_LANCASTERONLINE_PATTERN, "", "")],
        service_url="https://web.archive.org/web/*/",
    ),
]


class PaywallBypass(EmbedFixCog, name="Paywall Bypass", description="Bypass paywalls"):
    g = app_commands.Group(name="paywallbypass", description="PaywallBypass commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(
            bot,
            "Paywall Bypass",
            _HANDLERS,
            PaywallBypassConfig,
            bypass_button_mode=True,
        )

    def _bypass_embed(self, active):
        return discord.Embed(
            description=(
                f"Looks like this might be paywalled. You can read it for free using "
                f"**{active.name}** ({active.description}). "
                f"The bot just links to the service and doesn't store or cache anything."
            ),
            color=discord.Color.og_blurple(),
        )

    @g.command(name="toggle", description="Toggle paywall bypass for this server")
    @is_bot_owner_or_admin()
    async def toggle(self, interaction):
        await super().toggle(interaction)

    @g.command(
        name="service", description="Switch the paywall bypass service for this server"
    )
    @is_bot_owner_or_admin()
    async def service(self, interaction):
        await self._show_handler_select(interaction)


async def setup(bot):
    await bot.add_cog(PaywallBypass(bot))
