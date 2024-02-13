import os
import cachetools
import discord
import pyowm
import random
from opencage.geocoder import OpenCageGeocode
from discord.ext import commands
from cogs.lancocog import LancoCog


class Weather(LancoCog):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.geocoder = OpenCageGeocode(os.getenv("OPENCAGE_API_KEY"))
        self.owm = pyowm.OWM(os.getenv("OPENWEATHERMAP_API_KEY"))
        self.location_cache = {}
        self.weather_statuses = cachetools.TTLCache(
            maxsize=100, ttl=120
        )  # cache for 2 minutes

    async def get_coords(self, location):
        """Get the coordinates for a location"""
        query = None
        if location.isnumeric():  # zip code
            query = f"{location}, USA"
        else:
            query = location

        if query in self.location_cache:
            return self.location_cache[query]

        results = self.geocoder.geocode(query)
        coords = results[0]["geometry"]["lat"], results[0]["geometry"]["lng"]

        self.location_cache[query] = coords
        return coords

    async def get_weather(self, location):
        """Get the weather for a location"""
        coords = await self.get_coords(location)

        if coords in self.weather_statuses:
            return self.weather_statuses[coords]

        result = self.owm.weather_manager().weather_at_coords(coords[0], coords[1])
        if result:
            self.weather_statuses[coords] = result.weather
            return result.weather
        return None
    async def get_airstatus(self, location):
        """Get the Air Quality Index for a location"""
        coords = await self.get_coords(location)

        air_status = self.owm.airpollution_manager().air_quality_at_coords(coords[0], coords[1])
        return air_status

    @commands.hybrid_command()
    async def weather(self, ctx: commands.Context, location: str = "Lancaster, PA"):
        """Get the weather for a location"""
        air_status = await self.get_airstatus(location)
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
            fun = [":swimmer: :sun: :hot_face:",]
        elif 60 <= fahrenheit <= 80:
            fun = ["It's warm :t_shirt:",]
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
            concern = ["Good", "Moderate", "Unhealthy for sensitive groups", "Unhealthy", "Very unhealthy", "Hazardous"]
            embed.add_field(name="AQI", value=f"Level {air_status.aqi} {concern[air_status.aqi - 1]}", inline=False)

        embed.set_thumbnail(url=icon_url)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Weather(bot))
