import asyncio
import datetime
import os
import random
from calendar import weekday
from urllib.parse import urlencode

import aiofiles
import aiohttp
import cachetools
import discord
import googlemaps
import pytz
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from utils.command_utils import is_bot_owner

from .models import Bar


class BarHopper(LancoCog, name="BarHopper", description="Bar hopper commands"):
    barhopper_group = app_commands.Group(
        name="barhopper", description="Bar hopper commands"
    )

    est = pytz.timezone("US/Eastern")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot.database.create_tables([Bar])
        self.gmaps = googlemaps.Client(key=os.getenv("GMAPS_API_KEY"))
        self.bar_details_cache = cachetools.TTLCache(
            maxsize=100, ttl=60 * 60 * 24
        )  # 24 hours

    @barhopper_group.command(
        name="populate", description="Populate the database with bars"
    )
    @is_bot_owner()
    async def populate(self, interaction: discord.Interaction):
        bars = await self.get_nearby_bars()
        await self.populate_bars(bars)
        await interaction.response.send_message(
            f"Populated database with {len(bars)} bars"
        )

    @barhopper_group.command(name="search", description="Search for bars")
    async def search(self, interaction: discord.Interaction, search_term: str):
        bars = Bar.select().where(Bar.bar_name.contains(search_term)).limit(1)

        if bars and len(bars) > 0:
            for bar in bars:
                bar_embed, map_attachment = await self.create_bar_embed(bar)
                await interaction.response.send_message(
                    embed=bar_embed, file=map_attachment
                )
        else:
            await interaction.response.send_message(
                f"No bars found matching {search_term}"
            )

            #

    @barhopper_group.command(name="random", description="Suggests a random bar")
    async def random(self, interaction: discord.Interaction, count: int = 1):
        if random.randint(1, 30) == 1:
            await interaction.response.send_message("Dan's")
            return

        max_bars = 5
        if count > max_bars:
            await interaction.response.send_message(
                f"Please choose a number less than {max_bars}"
            )
            return

        random_bars = Bar.select().order_by(self.bot.database.random()).limit(count)

        if random_bars and len(random_bars) > 0:
            for random_bar in random_bars:
                bar_embed, map_attachment = await self.create_bar_embed(random_bar)
                await interaction.response.send_message(
                    embed=bar_embed, file=map_attachment
                )
        else:
            await interaction.response.send_message("No bars found")

    async def create_bar_embed(self, bar: Bar) -> discord.Embed:
        """Creates a discord embed for a bar"""

        # TODO move this elsewhere
        bar_details = self.bar_details_cache.get(bar.place_id, None)
        if not bar_details:
            bar_details = await self.get_current_bar_details(bar)
            self.bar_details_cache[bar.place_id] = bar_details

        current_opening_hours = bar_details.get("result", {}).get(
            "current_opening_hours", {}
        )
        current_hours_listing = current_opening_hours.get("weekday_text", [])
        is_open = current_opening_hours.get("open_now", False)
        periods = current_opening_hours.get("periods", [])
        closing_soon = False
        local_now = self.est.localize(datetime.datetime.now())
        current_day = weekday(local_now.year, local_now.month, local_now.day)
        current_day_name = self.est.localize(datetime.datetime.now()).strftime("%A")
        current_time = int(self.est.localize(datetime.datetime.now()).strftime("%H%M"))

        for period in periods:
            if period["close"]["day"] == current_day:
                closing_time = int(period["close"]["time"])
                if (
                    closing_time - current_time <= 100
                    and closing_time - current_time > 0
                ):
                    closing_soon = True
                break

        todays_hours = None
        if current_hours_listing:
            for index, day in enumerate(current_hours_listing):
                if day.startswith(current_day_name):
                    todays_hours = day
                    break

        website = bar_details.get("result", {}).get("website", None)

        phone = bar_details.get("result", {}).get("formatted_phone_number", None)

        map_attachment = discord.File(self.get_bar_map_path(bar), filename="map.png")

        maps_url = f"https://www.google.com/maps/search/"
        maps_params = {
            "api": 1,
            "query": bar.address,
        }

        embed = discord.Embed(
            title=f"{bar.bar_name}",
            description=f"{bar.address}",
            color=discord.Color.blue(),
            url=f"{maps_url}?{urlencode(maps_params)}",
        )

        if current_hours_listing:
            hours_str = todays_hours.split(": ")[1] if todays_hours else "Unknown"
            if closing_soon:
                hours_str += " (Closing Soon)"
            if not is_open:
                hours_str += " (Closed)"

            embed.add_field(
                name="Today's Hours",
                value=hours_str,
                inline=False,
            )

        embed.add_field(
            name="Rating",
            value=self.get_stars_rating(bar.rating),
        )

        embed.add_field(
            name="Price",
            value=self.get_price_level(bar.price_level),
        )

        if website:
            embed.add_field(
                name="Website",
                value=website,
                inline=False,
            )

        if phone:
            embed.add_field(
                name="Phone",
                value=phone,
                inline=False,
            )

        embed.set_thumbnail(url="attachment://map.png")

        return embed, map_attachment

    async def populate_bars(self, bars):
        Bar.delete().execute()

        for bar in bars:
            bar_model = Bar.create(
                bar_name=bar["name"],
                address=bar["address"],
                latitude=bar["latitude"],
                longitude=bar["longitude"],
                rating=bar["rating"],
                price_level=bar["price_level"],
                business_status=bar["business_status"],
                place_id=bar["place_id"],
            )

            # cache the map
            await self.get_map(bar_model)

    def get_bar_map_path(self, bar: Bar) -> str:
        filename = f"{bar.address}.png"

        map_cache_dir = os.path.join(self.get_cog_data_directory(), "bar_maps")
        if not os.path.exists(map_cache_dir):
            os.makedirs(map_cache_dir)

        full_path = os.path.join(map_cache_dir, filename)
        return full_path

    async def get_map(self, bar: Bar) -> str:
        """Returns a map of the bar"""

        map_width = 400
        map_height = 300

        url_params = {
            "center": f"{bar.latitude},{bar.longitude}",
            "zoom": 15,
            "scale": "1",
            "size": f"{map_width}x{map_height}",
            "type": "roadmap",
            "format": "png",
            "key": os.getenv("GMAPS_API_KEY"),
            "markers": f"{bar.latitude},{bar.longitude}",
        }

        url = f"https://maps.googleapis.com/maps/api/staticmap?{urlencode(url_params)}"

        filename = self.get_bar_map_path(bar)

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    f = await aiofiles.open(filename, mode="wb")
                    await f.write(await resp.read())
                    await f.close()

        return filename

    def get_stars_rating(self, rating: float) -> str:
        """Returns a string of stars based on the rating"""
        if rating is None:
            return "Unknown"
        num_stars = int(rating)
        return "⭐" * num_stars

    def get_price_level(self, price_level: int) -> str:
        """Returns a string of dollar signs based on the price level"""
        if price_level is None:
            return "Unknown"
        return "$" * price_level

    async def get_current_bar_details(self, bar: Bar):
        """Returns the current bar details via the Google Places API"""
        place_details = self.gmaps.place(bar.place_id)
        return place_details

    async def get_nearby_bars(self):
        """
        geocode_result = self.gmaps.geocode('city_name')
        location = geocode_result[0]['geometry']['location']
        city_coordinates = (location['lat'], location['lng'])
        """

        city_coordinates = (40.0382, -76.3055)

        bars = []
        next_page_token = None
        while True:
            places_result = self.gmaps.places_nearby(
                location=city_coordinates,
                radius=2200,
                type="bar",
                page_token=next_page_token if next_page_token else None,
            )

            for place in places_result.get("results", []):
                bar_info = {
                    "name": place["name"],
                    "address": place["vicinity"],
                    "latitude": place["geometry"]["location"]["lat"],
                    "longitude": place["geometry"]["location"]["lng"],
                    "rating": place.get("rating"),
                    "price_level": place.get("price_level"),
                    "business_status": place.get("business_status"),
                    "hours": place.get("opening_hours"),
                    "types": place["types"],
                    "place_id": place.get("place_id"),
                }
                bars.append(bar_info)

            next_page_token = places_result.get("next_page_token")
            if not next_page_token:
                break

            await asyncio.sleep(2)

        return bars


async def setup(bot):
    await bot.add_cog(BarHopper(bot))
