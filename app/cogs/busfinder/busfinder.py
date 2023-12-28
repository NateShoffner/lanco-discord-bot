import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from cogs.lancocog import LancoCog
from rrta import RRTAClient


class BusFinder(LancoCog):
    rrta_group = app_commands.Group(name="busfinder", description="RRTA Commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot = bot
        self.mystop_client = RRTAClient(aiohttp.ClientSession())

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


async def setup(bot):
    await bot.add_cog(BusFinder(bot))
