import datetime
import discord
from discord.ext import commands, tasks
from discord import app_commands
from sys import version_info as sysv
import lcwc
import aiohttp
from lcwc.category import IncidentCategory
from lcwc.arcgis import ArcGISClient as Client, ArcGISIncident as Incident

from cogs.lancocog import LancoCog


class Incidents(LancoCog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.client = Client()
        self.active_incidents = []
        self.last_updated = None

        self.incident_posts = {}

    @commands.Cog.listener()
    async def on_ready(self):
        print("Incidents cog loaded")
        await super().on_ready()
        self.get_incidents.change_interval(seconds=5)
        self.get_incidents.start()

    @tasks.loop(seconds=10)
    async def get_incidents(self):
        print("Getting incidents")

        async with aiohttp.ClientSession() as session:
            incidents = await self.client.get_incidents(session)

            for incident in incidents:
                new_incident = incident.number not in self.incident_posts
                if new_incident:
                    print(f"New incident: {incident.number}")
                    embed, map_attachment = await self.build_incident_embed(incident)
                    message = await self.bot.get_channel(1063533273692774472).send(
                        file=map_attachment, embed=embed
                    )
                    self.incident_posts[incident.number] = message.id
                    self.active_incidents.append(incident.number)

        self.last_updated = datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S")

    async def build_incident_embed(self, incident: Incident) -> discord.Embed:
        """Builds an embed for the given incident

        :param incident: The incident to build the embed for
        :return: The built embed object
        :rtype: discord.Embed
        """
        color_map = {
            IncidentCategory.FIRE: discord.Color.red(),
            IncidentCategory.MEDICAL: discord.Color.blue(),
            IncidentCategory.TRAFFIC: discord.Color.green(),
            IncidentCategory.UNKNOWN: discord.Color.light_gray(),
        }

        icon_map = {
            IncidentCategory.FIRE: "icons8-fire-truck-48.png",
            IncidentCategory.MEDICAL: "icons8-ambulance-48.png",
            IncidentCategory.TRAFFIC: "icons8-car-crash-48.png",
        }

        emoji_map = {
            IncidentCategory.FIRE: "🔥",
            IncidentCategory.MEDICAL: "🚑",
            IncidentCategory.TRAFFIC: "🚗",
            IncidentCategory.UNKNOWN: "❓",
        }

        # map_image = await self.map_cache.get_map(incident)
        # map_attachment = discord.File(map_image, filename='map.png')

        maps_url = f"https://www.google.com/maps/search/?api=1&query={incident.coordinates.longitude},{incident.coordinates.latitude}"

        embed = discord.Embed(
            title=f"Active {str(incident.category.value)} Incident",
            color=color_map[incident.category],
            url=maps_url,
            timestamp=incident.date,
        )

        embed.add_field(
            name="Category",
            value=f"{emoji_map[incident.category]} {str(incident.category.value)} Incident",
            inline=False,
        )
        embed.add_field(name="Location", value=f"{incident.intersection}", inline=False)
        embed.add_field(
            name="Description", value=f"{incident.description}", inline=False
        )
        # embed.add_field(name='Units Assigned', value='None' if len(incident.units) == 0 else '\n'.join(incident.units), inline=True)

        embed.set_footer(
            text=f'Incident #{incident.number} | {incident.date.strftime("%m/%d/%Y, %H:%M:%S")}'
        )

        # embed.set_thumbnail(url='attachment://incident.png')

        # embed.set_image(url='attachment://map.png')

        return (embed, None)

    @app_commands.command(name="status2", description="Show LCWC cog status")
    async def status(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Status", description="Incident Cog Status", color=0x00FF00
        )
        embed.add_field(name="Active Incidents", value=f"{len(self.active_incidents)}")
        embed.add_field(name="Last Updated", value=f'{self.last_updated or "Never"}')
        embed.add_field(name="Package Version", value=f"{lcwc.__version__}")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Incidents(bot))
