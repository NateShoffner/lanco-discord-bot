import asyncio
from typing import Optional
from urllib.parse import urlparse

import aiohttp
import discord
from bs4 import BeautifulSoup
from cogs.lancocog import LancoCog
from cogs.webpreview.models import WebPreviewConfig
from discord import app_commands
from discord.ext import commands
from pydantic import BaseModel
from utils.command_utils import is_bot_owner_or_admin


class PageDetails(BaseModel):
    title: Optional[str]
    description: Optional[str]


class WebPreview(LancoCog, name="WebPreview", description="WebPreview cog"):

    g = app_commands.Group(name="webpreview", description="Web preview commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot.database.create_tables([WebPreviewConfig])

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.content.startswith(self.bot.command_prefix):
            return

        # TODO handle multiple URLs in a single message
        url = None
        words = message.content.split()
        for word in words:
            p = urlparse(word)
            if p.scheme in ["http", "https"]:
                url = word
                break

        if not url:
            return

        config = WebPreviewConfig.get_or_none(guild_id=message.guild.id)
        if not config or not config.enabled:
            return

        # check if the url is already handled by another cog
        is_handled = self.bot.has_url_handler(url)
        if is_handled:
            return

        # wait a bit to see if discord will embed the link
        await asyncio.sleep(3)

        page_details = await self.get_page_details(url)
        if not page_details:
            return

        embed = discord.Embed(
            title=page_details.title, description=page_details.description, url=url
        )
        await message.channel.send(embed=embed)

    async def get_page_details(self, url: str) -> PageDetails:
        self.logger.info(f"Getting page details for {url}")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    self.logger.error(
                        f"Failed to get page details for {url}, status: {response.status}, reason: {response.reason}"
                    )
                    return None

                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")

                title = None
                description = None

                # first try meta tags
                title = soup.title.string
                meta_description = soup.find("meta", attrs={"name": "description"})
                if meta_description:
                    description = meta_description["content"]

                # try open graph tags
                og_title = soup.find("meta", attrs={"name": "og:title"})

                if og_title:
                    title = og_title["value"]
                og_description = soup.find("meta", attrs={"name": "og:description"})
                if og_description:
                    description = og_description["value"]

                return PageDetails(title=title, description=description)

    @g.command(name="toggle", description="Toggle Web previews for this server")
    @is_bot_owner_or_admin()
    async def toggle(self, interaction):
        config, created = WebPreviewConfig.get_or_create(guild_id=interaction.guild.id)
        if created or not config.enabled:
            config.enabled = True
            config.save()
            await interaction.response.send_message(
                f"Web Previews enabled for this server"
            )
        else:
            config.enabled = False
            config.save()
            await interaction.response.send_message(
                f"Web Previews disabled for this server"
            )


async def setup(bot):
    await bot.add_cog(WebPreview(bot))
