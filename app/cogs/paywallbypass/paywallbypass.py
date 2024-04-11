import re

from cogs.common.embedfixcog import EmbedFixCog
from discord import app_commands
from discord.ext import commands

from .models import PaywallBypassConfig

# TODO - make this configurable for various domains


class PaywallBypass(EmbedFixCog, name="Paywall Bypass", description="Bypass paywalls"):
    g = app_commands.Group(name="paywallbypass", description="PaywallBypass commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(
            bot,
            "Paywall Bypass",
            [
                EmbedFixCog.PatternReplacement(
                    re.compile(r"^(?!12ft.io)https://lancasteronline.com/(.+)"),
                    "https://lancasteronline.com/",
                    "https://12ft.io/https://lancasteronline.com/",
                ),
            ],
            PaywallBypassConfig,
        )

    @g.command(name="toggle", description="Toggle paywall bypass for this server")
    @commands.check_any(
        commands.has_permissions(administrator=True), commands.is_owner()
    )
    async def toggle(self, interaction):
        await super().toggle(interaction)


async def setup(bot):
    await bot.add_cog(PaywallBypass(bot))
