import asyncio
import os
import random
from datetime import datetime

import cachetools
import discord
import pyowm
import pytz
from cogs.lancocog import LancoCog
from discord.ext import commands
from opencage.geocoder import OpenCageGeocode, OpenCageGeocodeError

DEFAULT_LOCATION = "Lancaster, PA"

# How much of the One Call payload each view shows. It returns 48 hourly and
# 8 daily entries; both are trimmed to what fits an embed and stays readable.
HOURLY_HOURS = 12
DAILY_DAYS = 7

# One Call is billed per request, so a location's whole forecast is fetched
# once and both views are served from it.
FORECAST_TTL = 600

# OWM icon prefix -> embed colour. These are the full set OWM documents, but
# lookups go through _color_for so an icon we do not know about degrades to a
# neutral colour instead of raising KeyError mid-command.
ICON_COLORS = {
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
FALLBACK_COLOR = 0x95A5A6

ICON_EMOJI = {
    "01": "☀️",
    "02": "🌥️",
    "03": "☁️",
    "04": "☁️",
    "09": "🌧️",
    "10": "🌦️",
    "11": "⛈️",
    "13": "❄️",
    "50": "🌫️",
}
FALLBACK_EMOJI = "🌡️"


def _icon_key(icon_name: str) -> str:
    """The two-digit prefix of an OWM icon name, without its day/night suffix."""
    return (icon_name or "")[:2]


def _color_for(icon_name: str) -> int:
    return ICON_COLORS.get(_icon_key(icon_name), FALLBACK_COLOR)


def _emoji_for(icon_name: str) -> str:
    return ICON_EMOJI.get(_icon_key(icon_name), FALLBACK_EMOJI)


def _pop_suffix(pop: float) -> str:
    """Precipitation chance, omitted entirely when it is zero.

    OWM gives this as a 0-1 fraction. Printing "0%" on every dry day is noise,
    so a dry entry gets nothing at all.
    """
    if not pop:
        return ""
    return f"  💧 {round(pop * 100)}%"


def _format_hour(when: datetime) -> str:
    """Local hour as "8 AM".

    Built by hand rather than with strftime's %-I, which is glibc-only and
    raises on Windows, where the bot is developed.
    """
    return when.strftime("%I %p").lstrip("0")


def render_daily_row(
    when: datetime, icon_name: str, high: int, low: int, status: str, pop: float
) -> str:
    """One line of the daily view."""
    return (
        f"`{when:%a %m/%d}`  {_emoji_for(icon_name)}  "
        f"**{high}°** / {low}°  {status}{_pop_suffix(pop)}"
    )


def render_hourly_row(
    when: datetime, icon_name: str, temp: int, status: str, pop: float
) -> str:
    """One line of the hourly view."""
    return (
        f"`{_format_hour(when):>5}`  {_emoji_for(icon_name)}  "
        f"**{temp}°**  {status}{_pop_suffix(pop)}"
    )


def build_forecast_embed(location: str, one_call, hourly: bool):
    """Render a One Call result as an embed."""
    # Times come back as UTC timestamps. Rendering them in the bot's own
    # timezone would label a forecast for somewhere else with the wrong
    # hours, so each entry is converted to the location's timezone.
    tz = pytz.timezone(one_call.timezone)

    if hourly:
        entries = one_call.forecast_hourly[:HOURLY_HOURS]
        rows = [
            render_hourly_row(
                datetime.fromtimestamp(w.reference_time(), tz),
                w.weather_icon_name,
                round(w.temperature("fahrenheit")["temp"]),
                w.status,
                w.precipitation_probability,
            )
            for w in entries
        ]
        title = f"Hourly forecast for {location}"
    else:
        entries = one_call.forecast_daily[:DAILY_DAYS]
        rows = [
            render_daily_row(
                datetime.fromtimestamp(w.reference_time(), tz),
                w.weather_icon_name,
                round(w.temperature("fahrenheit")["max"]),
                round(w.temperature("fahrenheit")["min"]),
                w.status,
                w.precipitation_probability,
            )
            for w in entries
        ]
        title = f"{len(entries)}-day forecast for {location}"

    embed = discord.Embed(
        title=title,
        description="\n".join(rows),
        color=(_color_for(entries[0].weather_icon_name) if entries else FALLBACK_COLOR),
    )
    embed.set_footer(text=f"Times shown in {one_call.timezone}")
    return embed


class Weather(LancoCog, name="Weather", description="Fetches the weather"):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.geocoder = None
        self.owm = None
        self.location_cache = {}
        self.weather_statuses = cachetools.TTLCache(maxsize=100, ttl=120)
        self.air_statuses = cachetools.TTLCache(maxsize=100, ttl=120)
        self.forecasts = cachetools.TTLCache(maxsize=100, ttl=FORECAST_TTL)

    async def cog_load(self):
        opencage_key = os.getenv("OPENCAGE_API_KEY")
        owm_key = os.getenv("OPENWEATHERMAP_API_KEY")

        if not opencage_key or not owm_key:
            self.logger.warning(
                "Weather cog is missing OPENCAGE_API_KEY or OPENWEATHERMAP_API_KEY — commands will be disabled"
            )
            return

        self.geocoder = OpenCageGeocode(opencage_key)
        self.owm = pyowm.OWM(owm_key)

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
        if not results:
            return None

        coords = results[0]["geometry"]["lat"], results[0]["geometry"]["lng"]

        self.location_cache[query] = coords
        return coords

    async def get_weather(self, location):
        """Get the weather for a location"""
        coords = await self.get_coords(location)
        if not coords:
            return None

        self.logger.info(f"Fetching weather for coords: {coords}")

        if coords in self.weather_statuses:
            return self.weather_statuses[coords]

        try:
            result = self.owm.weather_manager().weather_at_coords(coords[0], coords[1])
            if result:
                self.weather_statuses[coords] = result.weather
                return result.weather

        except pyowm.commons.exceptions.NotFoundError as e:
            self.logger.error(f"Weather not found for coords: {coords} - {e}")
            return None

    async def get_air_status(self, location):
        """Get the Air Quality Index for a location"""
        coords = await self.get_coords(location)
        if not coords:
            return None

        if coords in self.air_statuses:
            return self.air_statuses[coords]

        air_status = self.owm.airpollution_manager().air_quality_at_coords(
            coords[0], coords[1]
        )

        if air_status:
            self.air_statuses[coords] = air_status
        return air_status

    @commands.hybrid_command()
    async def weather(self, ctx: commands.Context, location: str = DEFAULT_LOCATION):
        """Get the weather for a location"""
        if not self.geocoder or not self.owm:
            await ctx.send("Weather is not configured on this bot.")
            return

        try:
            air_status = await self.get_air_status(location)
            weather = await self.get_weather(location)
        except (OpenCageGeocodeError, pyowm.commons.exceptions.PyOWMError) as e:
            # A revoked key or a rate limit is a service problem, not a bad
            # location, so don't report it as one. The cause goes to the log.
            self.logger.error(f"Weather lookup failed for {location}: {e}")
            await ctx.send("Weather lookup is unavailable right now.")
            return

        if not weather:
            await ctx.send("Could not find weather for that location")
            return

        icon_url = (
            f"http://openweathermap.org/img/wn/{weather.weather_icon_name}@2x.png"
        )

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
            color=_color_for(weather.weather_icon_name),
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

    async def get_forecast(self, location):
        """Get the One Call forecast for a location"""
        coords = await self.get_coords(location)
        if not coords:
            return None

        if coords in self.forecasts:
            return self.forecasts[coords]

        self.logger.info(f"Fetching forecast for coords: {coords}")

        # pyowm is synchronous. The current-weather path calls it inline and
        # blocks the event loop for the length of the request; a forecast is
        # the larger payload of the two, so it goes to a thread.
        one_call = await asyncio.to_thread(
            self.owm.weather_manager().one_call, lat=coords[0], lon=coords[1]
        )

        if one_call:
            self.forecasts[coords] = one_call
        return one_call

    async def send_forecast(self, ctx: commands.Context, location: str, hourly: bool):
        """Shared body of the forecast commands."""
        if not self.geocoder or not self.owm:
            await ctx.send("Weather is not configured on this bot.")
            return

        # Geocoding plus One Call can outrun the 3 second interaction deadline.
        await ctx.defer()

        try:
            one_call = await self.get_forecast(location)
        except (OpenCageGeocodeError, pyowm.commons.exceptions.PyOWMError) as e:
            # Same split as the weather command: a revoked key or a rate limit
            # is a service problem, not a bad location.
            self.logger.error(f"Forecast lookup failed for {location}: {e}")
            await ctx.send("Forecast lookup is unavailable right now.")
            return

        if not one_call:
            await ctx.send("Could not find a forecast for that location")
            return

        await ctx.send(embed=build_forecast_embed(location, one_call, hourly))

    @commands.hybrid_group(name="forecast", invoke_without_command=True)
    async def forecast(
        self, ctx: commands.Context, *, location: str = DEFAULT_LOCATION
    ):
        """Get the multi-day forecast for a location"""
        await self.send_forecast(ctx, location, hourly=False)

    @forecast.command(name="daily")
    async def forecast_daily(
        self, ctx: commands.Context, *, location: str = DEFAULT_LOCATION
    ):
        """Get the multi-day forecast for a location"""
        await self.send_forecast(ctx, location, hourly=False)

    @forecast.command(name="hourly")
    async def forecast_hourly(
        self, ctx: commands.Context, *, location: str = DEFAULT_LOCATION
    ):
        """Get the hour-by-hour forecast for a location"""
        await self.send_forecast(ctx, location, hourly=True)


async def setup(bot):
    await bot.add_cog(Weather(bot))
