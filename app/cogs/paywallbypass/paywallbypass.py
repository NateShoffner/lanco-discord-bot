import asyncio
import re
from urllib.parse import urlparse

import discord
from cogs.common.embedfixcog import EmbedFixCog
from discord import app_commands
from discord.ext import commands
from utils.command_utils import is_bot_owner_or_admin

from .models import PaywallBypassConfig, PaywallPattern

KNOWN_PAYWALLED_DOMAINS = frozenset(
    {
        "lancasteronline.com",
    }
)

_URL_PATTERN = re.compile(r"https?://\S+")

_HANDLERS = [
    EmbedFixCog.Handler(
        "removepaywall", "Remove Paywall", "Uses removepaywall.com", []
    ),
    EmbedFixCog.Handler("archiveph", "Archive.ph", "Uses archive.ph", []),
    EmbedFixCog.Handler("wayback", "Wayback Machine", "Uses web.archive.org", []),
]

_SERVICE_URLS = {
    "removepaywall": "https://removepaywall.com/",
    "archiveph": "https://archive.ph/",
    "wayback": "https://web.archive.org/web/*/",
}


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _normalize_domain(raw: str) -> str:
    raw = raw.lower().strip()
    for prefix in ("https://", "http://"):
        if raw.startswith(prefix):
            raw = raw[len(prefix) :]
    raw = raw.removeprefix("www.").split("/")[0]
    return raw


class PaywallBypass(EmbedFixCog, name="Paywall Bypass", description="Bypass paywalls"):
    g = app_commands.Group(name="paywallbypass", description="PaywallBypass commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot, "Paywall Bypass", _HANDLERS, PaywallBypassConfig)
        self.bot.database.create_tables([PaywallPattern])
        self._pattern_cache: dict[int, set[str]] = {}

    def _guild_patterns(self, guild_id: int) -> set[str]:
        if guild_id not in self._pattern_cache:
            rows = PaywallPattern.select().where(PaywallPattern.guild_id == guild_id)
            self._pattern_cache[guild_id] = {r.pattern for r in rows}
        return self._pattern_cache[guild_id]

    def _is_paywalled(self, url: str, guild_id: int) -> bool:
        domain = _extract_domain(url)
        if not domain:
            return False
        if domain in KNOWN_PAYWALLED_DOMAINS:
            return True
        return any(
            domain == p or domain.endswith("." + p)
            for p in self._guild_patterns(guild_id)
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        if not message.channel.permissions_for(message.guild.me).embed_links:
            return

        match = _URL_PATTERN.search(message.content)
        if not match:
            return

        if self._is_within_angle_brackets(message.content, match):
            self.logger.info("URL is within angle brackets, ignoring")
            return

        if self._is_within_spoiler_tags(message.content, match):
            self.logger.info("URL is within spoiler tags, ignoring")
            return

        original_url = match.group(0).rstrip(".,;:!?\"')")

        if not self._is_paywalled(original_url, message.guild.id):
            return

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

    @g.command(name="addpattern", description="Add a domain to check for paywalls")
    @is_bot_owner_or_admin()
    async def addpattern(self, interaction: discord.Interaction, domain: str):
        domain = _normalize_domain(domain)
        if not domain:
            await interaction.response.send_message("Invalid domain.", ephemeral=True)
            return
        if PaywallPattern.get_or_none(
            PaywallPattern.guild_id == interaction.guild.id,
            PaywallPattern.pattern == domain,
        ):
            await interaction.response.send_message(
                f"`{domain}` is already in the list.", ephemeral=True
            )
            return
        PaywallPattern.create(guild_id=interaction.guild.id, pattern=domain)
        self._pattern_cache.pop(interaction.guild.id, None)
        await interaction.response.send_message(
            f"Added `{domain}` to paywall patterns.", ephemeral=True
        )

    @g.command(
        name="removepattern", description="Remove a domain from the paywall list"
    )
    @is_bot_owner_or_admin()
    async def removepattern(self, interaction: discord.Interaction, domain: str):
        domain = _normalize_domain(domain)
        deleted = (
            PaywallPattern.delete()
            .where(
                PaywallPattern.guild_id == interaction.guild.id,
                PaywallPattern.pattern == domain,
            )
            .execute()
        )
        self._pattern_cache.pop(interaction.guild.id, None)
        if deleted:
            await interaction.response.send_message(
                f"Removed `{domain}` from paywall patterns.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"`{domain}` was not in the list.", ephemeral=True
            )

    @g.command(
        name="patterns",
        description="List custom domain patterns configured for this server",
    )
    @is_bot_owner_or_admin()
    async def patterns(self, interaction: discord.Interaction):
        guild_patterns = self._guild_patterns(interaction.guild.id)
        if not guild_patterns:
            await interaction.response.send_message(
                "No custom patterns configured. Only the built-in known-paywalls list is active.",
                ephemeral=True,
            )
            return
        listed = "\n".join(f"• `{p}`" for p in sorted(guild_patterns))
        await interaction.response.send_message(
            f"**Custom paywall patterns:**\n{listed}", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(PaywallBypass(bot))
