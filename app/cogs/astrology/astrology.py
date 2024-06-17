import datetime
import os

import aiohttp
import discord
from bs4 import BeautifulSoup
from cogs.lancocog import LancoCog
from discord import Interaction, app_commands
from discord.ext import commands
from discord.ui import Select, View
from openai import AsyncOpenAI
from pydantic import BaseModel
from pyrsistent import discard


class Horrorscope(BaseModel):
    description: str
    day: datetime.datetime


class Astrology(LancoCog, name="Astrology", description="Astrology cog"):

    g = app_commands.Group(name="horrorscope", description="Horrorscope commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.daily_cache = {}  # cache for daily horrorscopes

    @g.command(name="get", description="Get a horrorscope for a sign")
    async def get(self, interaction: Interaction):
        options = []
        signs = {
            "Aries": "♈",
            "Taurus": "♉",
            "Gemini": "♊",
            "Cancer": "♋",
            "Leo": "♌",
            "Virgo": "♍",
            "Libra": "♎",
            "Scorpio": "♏",
            "Sagittarius": "♐",
            "Capricorn": "♑",
            "Aquarius": "♒",
            "Pisces": "♓",
        }

        sorted_signs = {
            k: v for k, v in sorted(signs.items(), key=lambda item: item[0])
        }

        for sign, emoji in sorted_signs.items():
            options.append(discord.SelectOption(label=sign, value=sign, emoji=emoji))

        select = Select(placeholder="Choose a Sign", options=options)
        select.callback = self.callback

        view = View()
        view.add_item(select)

        await interaction.channel.typing()
        await interaction.response.send_message(view=view, ephemeral=True)

    async def get_horrorscope(self, sign: str) -> Horrorscope:
        # TODO maybe let's not scrape for this

        if sign.lower() in self.daily_cache:
            if (
                self.daily_cache[sign.lower()].day.date()
                == datetime.datetime.now().date()
            ):
                return self.daily_cache[sign.lower()]
            else:
                self.daily_cache.pop(sign.lower())

        signs = {
            "aries": 1,
            "taurus": 2,
            "gemini": 3,
            "cancer": 4,
            "leo": 5,
            "virgo": 6,
            "libra": 7,
            "scorpio": 8,
            "sagittarius": 9,
            "capricorn": 10,
            "aquarius": 11,
            "pisces": 12,
        }
        url = f"https://www.horoscope.com/us/horoscopes/general/horoscope-general-daily-today.aspx?sign={signs[sign.lower()]}"

        async with aiohttp.ClientSession() as session:

            async with session.get(url) as response:

                if response.status != 200:
                    return None

                html = await response.text()

                soup = BeautifulSoup(html, "html.parser")

                container = soup.find("p")
                today = container.text

                if not today or len(today) == 0:
                    return None

                h = Horrorscope(description=today, day=datetime.datetime.now())
                self.daily_cache[sign.lower()] = h
                return h

    async def callback(self, interaction: discord.Interaction):
        sign_value = interaction.data["values"][0]

        await interaction.channel.typing()

        h = await self.get_horrorscope(sign_value)
        if h:
            await interaction.response.send_message(h.description, ephemeral=True)
        else:
            await interaction.response.send_message(
                "Could not get horrorscope", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Astrology(bot))
