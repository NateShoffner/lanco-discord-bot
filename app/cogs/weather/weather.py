import os
import random

import cachetools
import discord
import pyowm
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from opencage.geocoder import OpenCageGeocode
from pydantic import BaseModel

from .models import WeatherUserConfig


class Cooordinates(BaseModel):
    lat: float
    lon: float
    name: str

    class Config:
        frozen = True
        allow_mutation = False


class Weather(LancoCog, name="Weather", description="Fetches the weather"):
    weather_group = app_commands.Group(
        name="weather",
        description="Weather commands",
    )

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.geocoder = OpenCageGeocode(os.getenv("OPENCAGE_API_KEY"))
        self.owm = pyowm.OWM(os.getenv("OPENWEATHERMAP_API_KEY"))
        self.location_cache = dict[str, Cooordinates]()  # location -> coordinates
        self.weather_statuses = cachetools.TTLCache(
            maxsize=100, ttl=120
        )  # cache for 2 minutes
        self.air_statuses = cachetools.TTLCache(
            maxsize=100, ttl=120
        )  # cache for 2 minutes
        self.bot.database.create_tables([WeatherUserConfig])

    @weather_group.command(
        name="set_location", description="Set your default weather location"
    )
    async def set_location(self, interaction: discord.Interaction, location: str):
        """Set your default weather location"""

        # first check if the coords are valid
        try:
            coords = await self.get_coords(location)
        except Exception as e:
            self.logger.error(f"Error getting coordinates for {location}: {e}")
            embed = discord.Embed(
                title="Error",
                description=f"Could not find location: {location}. Please try again.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        user_id = interaction.user.id
        user_config, created = WeatherUserConfig.get_or_create(user_id=user_id)
        user_config.user_location = location
        user_config.location = coords.name
        user_config.lon = coords.lon
        user_config.lat = coords.lat
        user_config.save()

        embed = discord.Embed(
            title="Weather Location Set",
            description=f"You have successfully set your default weather location",
            color=discord.Color.green(),
        )
        embed.add_field(name="Location", value=f"{coords.name}", inline=False)
        embed.add_field(name="Latitude", value=f"{coords.lat}", inline=True)

        embed.add_field(name="Longitude", value=f"{coords.lon}", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def get_coords(self, location) -> Cooordinates:
        """Get the coordinates for a location"""
        query = None
        if location.isnumeric():  # zip code
            query = f"{location}, USA"
        else:
            query = location

        if query in self.location_cache:
            return self.location_cache[query]

        results = self.geocoder.geocode(query)

        first_result = results[0] if results else None

        coords = Cooordinates(
            lat=first_result["geometry"]["lat"],
            lon=first_result["geometry"]["lng"],
            name=first_result["components"]["_normalized_city"],
        )
        self.location_cache[query] = coords
        return coords

    async def get_weather(self, location):
        """Get the weather for a location"""
        coords = await self.get_coords(location)

        if coords in self.weather_statuses:
            return self.weather_statuses[coords]

        result = self.owm.weather_manager().weather_at_coords(coords.lat, coords.lon)
        if result:
            self.weather_statuses[coords] = result.weather
            return result.weather
        return None

    async def get_air_status(self, location):
        """Get the Air Quality Index for a location"""
        coords = await self.get_coords(location)

        if coords in self.air_statuses:
            return self.air_statuses[coords]

        air_status = self.owm.airpollution_manager().air_quality_at_coords(
            coords.lat, coords.lon
        )

        if air_status:
            self.air_statuses[coords] = air_status
        return air_status

    @commands.command(name="weather", help="Get the weather for a location")
    async def weather(self, ctx: commands.Context, location: str = "Lancaster, PA"):
        """Get the weather for a location"""
        user_config = WeatherUserConfig.get_or_none(user_id=ctx.author.id)
        if user_config and user_config.location:
            location = user_config.location

        air_status = await self.get_air_status(location)
        weather = await self.get_weather(location)

        if not weather:
            await ctx.send("Could not find weather for that location")
            return

        icon_url = (
            f"http://openweathermap.org/img/wn/{weather.weather_icon_name}@2x.png"
        )

        color_map = {
            "01": 0xFFFF00,  # clear
            "02": 0xFFFF00,  # few clouds
            "03": 0xFFFF00,  # scattered clouds
            "04": 0xFFFF00,  # broken clouds
            "09": 0x0000FF,  # shower rain
            "10": 0x0000FF,  # rain
            "11": 0x0000FF,  # thunderstorm
            "13": 0x00FFFF,  # snow
            "50": 0x00FFFF,  # mist
        }

        desc = weather.status
        if weather.detailed_status.lower() != weather.status.lower():
            desc += f" ({weather.detailed_status})"

        fahrenheit = int(weather.temperature("fahrenheit")["temp"])
        if fahrenheit > 80:
            fun = [
                ":swimmer: :sun: :hot_face:",
            ]
        elif 60 <= fahrenheit <= 80:
            fun = [
                "It's warm :t_shirt:",
            ]
        elif fahrenheit > 40:
            fun = ["It's hoodie weather", "Bonfire weather :fire:"]
        else:
            fun = ["It's fucking cold :cold_face:", "frigid"]
        embed = discord.Embed(
            title=f"Weather in {location}",
            description=desc,
            color=color_map[weather.weather_icon_name[:2]],
        )
        embed.add_field(
            name="",
            value=f"{random.choice(fun)}",
            inline=False,
        )
        embed.add_field(
            name="Temperature",
            value=f"{fahrenheit}°F (Feels like {int(weather.temperature('fahrenheit')['feels_like'])}°F)",
            inline=False,
        )
        embed.add_field(
            name="Wind Speed", value=f"{int(weather.wind()['speed'])} mph", inline=False
        )
        embed.add_field(name="Humidity", value=f"{weather.humidity}%", inline=False)
        embed.add_field(name="Cloudiness", value=f"{weather.clouds}%", inline=False)
        embed.add_field(
            name="Pressure", value=f"{weather.pressure['press']} hPa", inline=False
        )
        if air_status:
            concern = [
                "Good",
                "Moderate",
                "Unhealthy for sensitive groups",
                "Unhealthy",
                "Very unhealthy",
                "Hazardous",
            ]
            embed.add_field(
                name="AQI",
                value=f"Level {air_status.aqi} ({concern[air_status.aqi - 1]})",
                inline=False,
            )

        embed.set_thumbnail(url=icon_url)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Weather(bot))
