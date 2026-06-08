import asyncio
import re

import aiohttp
import discord
from bs4 import BeautifulSoup
from cogs.common.embedfixcog import EmbedFixCog
from cogs.lancocog import UrlHandler
from discord import app_commands
from discord.ext import commands
from main import LancoBot
from utils.command_utils import is_bot_owner_or_admin

from .models import FacebookEmbedConfig

# First-path segments that denote content types (not page vanity slugs), so a
# bare facebook.com/<slug> is only a page when <slug> isn't one of these.
RESERVED_SLUGS = (
    "events",
    "reel",
    "reels",
    "watch",
    "stories",
    "story",
    "story.php",
    "share",
    "groups",
    "marketplace",
    "gaming",
    "media",
    "photo.php",
    "permalink.php",
    "profile.php",
)
_RESERVED_LOOKAHEAD = r"(?!(?:" + "|".join(RESERVED_SLUGS) + r")(?:[/?]|$))"
_PAGE_SHAPE = _RESERVED_LOOKAHEAD + r"[^/\s?]+/?(?:\?\S*)?(?=\s|$)"

# events, posts, and pages are handled natively (facebed returns a login card
# for events/pages, and wraps posts in a noisy author/stats header). Stories are
# skipped entirely (login-walled; no service or API can embed them), so facebed
# would only produce a useless "Log in to view" card. NOT_NATIVE keeps all of
# those out of the facebed rewrite; everything else (reels, videos, share, ...)
# still rewrites to facebed.
NOT_NATIVE = (
    r"(?!events/|stories/|story(?:\.php|/)|[^/\s]+/posts/|" + _PAGE_SHAPE + r")"
)

EVENT_PATTERN = re.compile(r"https?://(?:www\.|web\.|m\.)?facebook\.com/events/\S+")
POST_PATTERN = re.compile(
    r"https?://(?:www\.|web\.|m\.)?facebook\.com/[^/\s]+/posts/\S+"
)
PAGE_PATTERN = re.compile(r"https?://(?:www\.|web\.|m\.)?facebook\.com/" + _PAGE_SHAPE)

_OG_PROPERTY = re.compile(r"^og:")

# Facebook serves OG data inconsistently across user-agents, so the native
# handlers try both (see get_og_tags_resilient).
FB_CRAWLER_UA = "facebookexternalhit/1.1"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

FB_BLUE = discord.Color.from_rgb(8, 102, 255)


class FacebookEmbed(
    EmbedFixCog, name="Facebook Embed Fix", description="Fix Facebook embeds"
):
    g = app_commands.Group(name="facebookembed", description="FacebookEmbed commands")

    def __init__(self, bot: LancoBot):
        # The base EmbedFixCog does a single string replace of `original` with
        # `replacement`. To avoid leaving the www./m./web. prefix attached to the
        # replacement host, each host form is matched and swapped in full.
        facebook_pattern = re.compile(
            r"https?://(?:www\.|web\.|m\.)?facebook\.com/" + NOT_NATIVE + r"\S+"
        )

        www_facebook_pattern = re.compile(
            r"https?://www\.facebook\.com/" + NOT_NATIVE + r"\S+"
        )
        web_facebook_pattern = re.compile(
            r"https?://web\.facebook\.com/" + NOT_NATIVE + r"\S+"
        )
        m_facebook_pattern = re.compile(
            r"https?://m\.facebook\.com/" + NOT_NATIVE + r"\S+"
        )
        bare_facebook_pattern = re.compile(
            r"https?://facebook\.com/" + NOT_NATIVE + r"\S+"
        )

        fb_watch_pattern = re.compile(r"https?://fb\.watch/\S+")

        super().__init__(
            bot,
            "Facebook Embed Fix",
            [
                EmbedFixCog.PatternReplacement(
                    www_facebook_pattern,
                    "www.facebook.com",
                    "facebed.seria.moe",
                ),
                EmbedFixCog.PatternReplacement(
                    web_facebook_pattern,
                    "web.facebook.com",
                    "facebed.seria.moe",
                ),
                EmbedFixCog.PatternReplacement(
                    m_facebook_pattern,
                    "m.facebook.com",
                    "facebed.seria.moe",
                ),
                EmbedFixCog.PatternReplacement(
                    bare_facebook_pattern,
                    "facebook.com",
                    "facebed.seria.moe",
                ),
                EmbedFixCog.PatternReplacement(
                    fb_watch_pattern,
                    "fb.watch",
                    "facebed.seria.moe/fb.watch",
                ),
            ],
            FacebookEmbedConfig,
        )

        bot.register_url_handler(
            UrlHandler(
                url_pattern=facebook_pattern,
                cog=self,
                example_url="https://www.facebook.com/watch/?v=10153231379946729",
            )
        )
        bot.register_url_handler(
            UrlHandler(
                url_pattern=fb_watch_pattern,
                cog=self,
                example_url="https://fb.watch/abcd1234/",
            )
        )
        bot.register_url_handler(
            UrlHandler(
                url_pattern=EVENT_PATTERN,
                cog=self,
                example_url="https://www.facebook.com/events/1786466945406243/",
            )
        )
        bot.register_url_handler(
            UrlHandler(
                url_pattern=POST_PATTERN,
                cog=self,
                example_url="https://www.facebook.com/facebook/posts/123456789",
            )
        )
        bot.register_url_handler(
            UrlHandler(
                url_pattern=PAGE_PATTERN,
                cog=self,
                example_url="https://www.facebook.com/facebook",
            )
        )

    @g.command(name="toggle", description="Toggle Facebook embed fix for this server")
    @is_bot_owner_or_admin()
    async def toggle(self, interaction):
        await super().toggle(interaction)

    def _matched_url(self, message: discord.Message, pattern: re.Pattern):
        """Return the URL a native handler should act on, or None to skip.

        Applies the shared guards (bot author, embed permission, angle-bracket
        and spoiler suppression, and the per-guild enabled flag).
        """
        if message.author.bot:
            return None
        if not message.channel.permissions_for(message.guild.me).embed_links:
            return None

        match = pattern.search(message.content)
        if not match:
            return None
        if self._is_within_angle_brackets(message.content, match):
            return None
        if self._is_within_spoiler_tags(message.content, match):
            return None

        config = self.config_model.get_or_none(guild_id=message.guild.id)
        if not config or not config.enabled:
            return None

        return match.group(0)

    async def _send_fix(self, message: discord.Message, **send_kwargs):
        """Reply with the fixed embed(s) and suppress the original's preview."""
        fixed_msg = await message.reply(**send_kwargs)
        self.fixed_messages[message.id] = fixed_msg.id
        if message.channel.permissions_for(message.guild.me).manage_messages:
            await message.edit(suppress=True)

    @commands.Cog.listener("on_message")
    async def handle_events(self, message: discord.Message):
        """Native embed for event links (facebed only returns a login card)."""
        url = self._matched_url(message, EVENT_PATTERN)
        if not url:
            return

        self.logger.info(f"Building native event embed for {url}")
        og = await self.get_og_tags_resilient(url)
        if not og.get("og:title"):
            self.logger.info(f"No usable OpenGraph data for {url}")
            return

        embed = discord.Embed(
            title=og.get("og:title"),
            description=og.get("og:description"),
            url=og.get("og:url", url),
            color=FB_BLUE,
        )
        if og.get("images"):
            embed.set_image(url=og["images"][0])
        embed.set_footer(text="Facebook Event")
        await self._send_fix(message, embed=embed)

    @commands.Cog.listener("on_message")
    async def handle_posts(self, message: discord.Message):
        """Native gallery embed for post links, dropping facebed's noisy header.

        Images come from facebed (it lists every photo as an og:image); the post
        text comes from Facebook's own og:description. Falls back to the facebed
        link if neither source yields anything usable.
        """
        url = self._matched_url(message, POST_PATTERN)
        if not url:
            return

        self.logger.info(f"Building native post embed for {url}")
        facebed_url = re.sub(
            r"(?:www\.|web\.|m\.)?facebook\.com", "facebed.seria.moe", url
        )

        facebed_og, facebook_og = await asyncio.gather(
            self.get_og_tags(facebed_url),
            self.get_og_tags(url, user_agent=BROWSER_UA),
        )

        title = facebed_og.get("og:title") or facebook_og.get("og:title")
        description = facebook_og.get("og:description") or facebed_og.get(
            "og:description"
        )
        images = facebed_og.get("images") or facebook_og.get("images") or []

        if not title and not images:
            self.logger.info(f"No usable data for {url}, falling back to facebed link")
            await self._send_fix(message, content=facebed_url)
            return

        embeds = self._build_gallery_embeds(title, description, url, images)
        await self._send_fix(message, embeds=embeds)

    @commands.Cog.listener("on_message")
    async def handle_pages(self, message: discord.Message):
        """Native embed for bare page/profile links (facebed returns a login card).

        Stays silent if nothing usable is scraped, rather than posting that card.
        """
        url = self._matched_url(message, PAGE_PATTERN)
        if not url:
            return

        self.logger.info(f"Building native page embed for {url}")
        og = await self.get_og_tags_resilient(url)
        if not og.get("og:title"):
            self.logger.info(f"No usable OpenGraph data for {url}")
            return

        embed = discord.Embed(
            title=og.get("og:title"),
            description=og.get("og:description"),
            url=og.get("og:url", url),
            color=FB_BLUE,
        )
        if og.get("images"):
            embed.set_thumbnail(url=og["images"][0])
        embed.set_footer(text="Facebook")
        await self._send_fix(message, embed=embed)

    @staticmethod
    def _build_gallery_embeds(
        title: str, description: str, url: str, images: list
    ) -> list:
        """Build a multi-image gallery.

        Discord merges consecutive embeds sharing the same ``url`` into one
        image grid (max four), so each extra image is an empty embed reusing the
        primary embed's url.
        """
        if title:
            title = title[:256]
        if description and len(description) > 4096:
            description = description[:4093] + "..."

        primary = discord.Embed(
            title=title,
            description=description,
            url=url,
            color=FB_BLUE,
        )
        primary.set_footer(text="Facebook")
        if images:
            primary.set_image(url=images[0])

        embeds = [primary]
        for image in images[1:4]:
            extra = discord.Embed(url=url)
            extra.set_image(url=image)
            embeds.append(extra)
        return embeds

    async def get_og_tags_resilient(self, url: str) -> dict:
        """Fetch OG data, retrying with the other UA if the first returns no title."""
        for user_agent in (FB_CRAWLER_UA, BROWSER_UA):
            og = await self.get_og_tags(url, user_agent=user_agent)
            if og.get("og:title"):
                return og
        return {}

    async def get_og_tags(self, url: str, user_agent: str = FB_CRAWLER_UA) -> dict:
        """Return og:* tags as a dict, plus an "images" list of every og:image.

        Returns {} on any fetch error.
        """
        headers = {"User-Agent": user_agent}
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        self.logger.error(
                            f"Failed to fetch {url}: status {response.status}"
                        )
                        return {}
                    html = await response.text()
        except aiohttp.ClientError as e:
            self.logger.error(f"Error fetching {url}: {e}")
            return {}

        soup = BeautifulSoup(html, "html.parser")
        tags = {"images": []}
        for meta in soup.find_all("meta", property=_OG_PROPERTY):
            content = meta.get("content")
            if not content:
                continue
            if meta["property"] == "og:image":
                if content not in tags["images"]:
                    tags["images"].append(content)
            else:
                tags[meta["property"]] = content
        return tags


async def setup(bot):
    await bot.add_cog(FacebookEmbed(bot))
