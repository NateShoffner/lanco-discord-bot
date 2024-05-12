import datetime
import math
import os

import aiohttp
import discord
import googlemaps
import pytz
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from rrta import ModeShiftClient, RRTAClient
from rrta.models.modeshift import Coordinate as ModeShiftCoordinate
from rrta.models.modeshift import Mode


class BusFinder(LancoCog):
    rrta_group = app_commands.Group(name="busfinder", description="RRTA Commands")

    est = pytz.timezone("US/Eastern")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot = bot
        self.gmaps = googlemaps.Client(key=os.getenv("GMAPS_API_KEY"))
        self.mystop_client = RRTAClient(aiohttp.ClientSession())
        self.modeshift_client = ModeShiftClient(
            aiohttp.ClientSession(), os.getenv("MODESHIFT_CLIENT_ID")
        )

    @rrta_group.command(name="routes", description="Get all routes")
    async def rrta(self, interaction: discord.Interaction):
        routes = await self.mystop_client.get_all_routes()

        embed = discord.Embed(
            title="RRTA Routes", description="List of all RRTA routes"
        )
        route_list = []
        for route in routes:
            schedule_url = (
                f"https://www.redrosetransit.com/schedules/route-{route.RouteId}"
            )
            route_list.append(
                f"**{route.LongName} {route.RouteId}**: [Schedule]({schedule_url})"
            )
        embed = discord.Embed(
            title=f"RRTA Routes",
            description="\n".join([f"{route}" for route in route_list]),
        )
        await interaction.response.send_message(embed=embed)

    @rrta_group.command(name="plan", description="Plan a trip")
    async def plan(
        self, interaction: discord.Interaction, origin: str, destination: str
    ):
        qualifiers = ["lancaster", "pa", "pennsylvania"]

        if not any(qualifier in origin.lower() for qualifier in qualifiers):
            origin += " Lancaster, PA"

        if not any(qualifier in destination.lower() for qualifier in qualifiers):
            destination += " Lancaster, PA"

        origin_coords = self.gmaps.geocode(origin)[0]["geometry"]["location"]

        if origin_coords is None:
            await interaction.response.send_message(
                f"Could not find a location named {origin}"
            )
            return

        destination_coords = self.gmaps.geocode(destination)[0]["geometry"]["location"]
        if destination_coords is None:
            await interaction.response.send_message(
                f"Could not find a location named {destination}"
            )
            return

        planResponse = await self.modeshift_client.get_plan(
            ModeShiftCoordinate(origin_coords["lat"], origin_coords["lng"]),
            ModeShiftCoordinate(destination_coords["lat"], destination_coords["lng"]),
        )

        plan = planResponse.plan

        if plan is None:
            await interaction.response.send_message(
                f"Could not find a plan from {origin} to {destination}"
            )
            return

        itinerary_list = []
        for it in plan.itineraries:
            start_time = datetime.datetime.fromtimestamp(it.startTime).astimezone(
                self.est
            )
            end_time = datetime.datetime.fromtimestamp(it.endTime).astimezone(self.est)

            duration = datetime.timedelta(seconds=it.duration)

            itinerary_list.append(
                f"{start_time:%I:%M %p} - {end_time:%I:%M %p} \t{math.ceil(duration.seconds / 60)} min"
            )

            leg_builder = ""
            has_more = False
            for i, leg in enumerate(it.legs):
                if leg.mode == Mode.WALK:
                    leg_builder += f"Walk {int(leg.duration / 60) }"

                if leg.mode == Mode.BUS:
                    leg_builder += f"Bus {leg.route}"

                has_more = i < len(it.legs) - 1

                if has_more:
                    leg_builder += " ➡️ "

            itinerary_list.append(leg_builder)

        embed = discord.Embed(
            title=f"RRTA trip from {origin} to {destination}",
            description="\n".join([f"{itinerary}" for itinerary in itinerary_list]),
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(BusFinder(bot))
