import asyncio
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
    ),
    EmbedFixCog.Handler(
        "archiveph",
        "Archive.ph",
        "Uses archive.ph",
        [EmbedFixCog.PatternReplacement(_LANCASTERONLINE_PATTERN, "", "")],
    ),
    EmbedFixCog.Handler(
        "wayback",
        "Wayback Machine",
        "Uses web.archive.org",
        [EmbedFixCog.PatternReplacement(_LANCASTERONLINE_PATTERN, "", "")],
    ),
]

_SERVICE_URLS = {
    "removepaywall": "https://removepaywall.com/",
    "archiveph": "https://archive.ph/",
    "wayback": "https://web.archive.org/web/*/",
}


class PaywallBypass(EmbedFixCog, name="Paywall Bypass", description="Bypass paywalls"):
    g = app_commands.Group(name="paywallbypass", description="PaywallBypass commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot, "Paywall Bypass", _HANDLERS, PaywallBypassConfig)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not message.guild:
            return

        if not message.channel.permissions_for(message.guild.me).embed_links:
            return

        match = _LANCASTERONLINE_PATTERN.search(message.content)
        if not match:
            return

        if self._is_within_angle_brackets(message.content, match):
            self.logger.info("URL is within angle brackets, ignoring")
            return

        if self._is_within_spoiler_tags(message.content, match):
            self.logger.info("URL is within spoiler tags, ignoring")
            return

        original_url = match.group(0)

        self.logger.info(
            f"Found paywalled URL: {original_url} - waiting {self.wait_time}s"
        )
        await asyncio.sleep(self.wait_time)

        message = await message.channel.fetch_message(message.id)

        config = self.config_model.get_or_none(guild_id=message.guild.id)
        if not config or not config.enabled:
            self.logger.info("Paywall bypass not enabled for this server")
            return

        active = self._active_handler(config)
        service_url = _SERVICE_URLS[active.id]
        bypass_url = service_url + original_url

        self.logger.info(f"Bypass via '{active.id}': {original_url} -> {bypass_url}")

        embed = discord.Embed(
            description=(
                f"Looks like this might be paywalled for some users. You can read it for free using "
                f"**{active.name}** ({active.description}). "
                f"The bot just links to the service and doesn't store or cache anything."
            ),
            color=discord.Color.og_blurple(),
        )
        view = discord.ui.View(timeout=None)
        view.add_item(
            discord.ui.Button(
                label=f"Read via {active.name}",
                url=bypass_url,
                style=discord.ButtonStyle.link,
                emoji="🔓",
            )
        )
        fixed_msg = await message.reply(embed=embed, view=view, mention_author=False)
        self.fixed_messages[message.id] = fixed_msg.id

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
