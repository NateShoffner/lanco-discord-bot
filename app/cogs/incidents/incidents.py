import datetime
import os
import aiofiles
import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
from lcwc.category import IncidentCategory
from lcwc.arcgis import ArcGISClient as Client, ArcGISIncident as Incident
import pytz
from .models import IncidentConfig
from urllib.parse import urlencode
from cogs.lancocog import LancoCog
import pkg_resources


class Incidents(LancoCog):
    incidents_group = app_commands.Group(
        name="incidents", description="Incident commands"
    )

    est = pytz.timezone("US/Eastern")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.bot.database.create_tables([IncidentConfig])

        self.client = Client()
        self.active_incidents = []
        self.last_updated = None

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
                subbed_guilds = IncidentConfig.select().where(
                    IncidentConfig.enabled == True
                )

                for guild in subbed_guilds:
                    # TODO shouldn't need to do this after upstream fix is applied
                    if (
                        guild.last_known_incident
                        and guild.last_known_incident >= incident.number
                    ):
                        continue

                    print(f"New incident: {incident.number} for {guild.guild_id}")
                    embed, map_attachment = await self.build_incident_embed(incident)
                    message = await self.bot.get_channel(guild.channel_id).send(
                        file=map_attachment, embed=embed
                    )

                    guild.last_known_incident = incident.number
                    guild.save()

                self.last_updated = datetime.datetime.now()
                self.active_incidents = incidents

        self.last_updated = datetime.datetime.now()

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

        emoji_map = {
            IncidentCategory.FIRE: "🔥",
            IncidentCategory.MEDICAL: "🚑",
            IncidentCategory.TRAFFIC: "🚗",
            IncidentCategory.UNKNOWN: "❓",
        }

        map_image = await self.get_map(incident)
        map_attachment = discord.File(map_image, filename="map.png")

        maps_url = f"https://www.google.com/maps/search/?api=1&query={incident.coordinates.latitude},{incident.coordinates.longitude}"

        incident_time = incident.date.astimezone(self.est)

        embed = discord.Embed(
            title=f"Active {str(incident.category.value)} Incident",
            color=color_map[incident.category],
            url=maps_url,
            timestamp=incident_time,
        )

        full_location = f"{incident.municipality}"
        if incident.intersection:
            full_location = f"{incident.intersection}\n{full_location}"

        embed.add_field(
            name="Category",
            value=f"{emoji_map[incident.category]} {str(incident.category.value)} Incident",
            inline=False,
        )
        embed.add_field(name="Location", value=f"{full_location}", inline=False)
        embed.add_field(
            name="Description", value=f"{incident.description}", inline=False
        )

        embed.add_field(name="Agency", value=f"{incident.agency}", inline=False)

        embed.add_field(
            name="Units Assigned",
            value="None"
            if len(incident.units) == 0
            else "\n".join([unit.full_name for unit in incident.units]),
            inline=True,
        )

        embed.set_footer(
            text=f"Incident: {incident.number} | Priority: {incident.priority}"
        )

        embed.set_image(url="attachment://map.png")

        return (embed, map_attachment)

    async def get_map(self, incident: Incident) -> None:
        """Downloads the map image for the given incident and caches it."""

        map_width = 400
        map_height = 300

        url_params = {
            "center": f"{incident.coordinates.latitude},{incident.coordinates.longitude}",
            "zoom": 15,
            "scale": "1",
            "size": f"{map_width}x{map_height}",
            "type": "roadmap",
            "format": "png",
            "key": os.getenv("GMAPS_API_KEY"),
            "markers": f"{incident.coordinates.latitude},{incident.coordinates.longitude}",
        }

        url = f"https://maps.googleapis.com/maps/api/staticmap?{urlencode(url_params)}"

        filename = f"{incident.number}.png"

        map_cache_dir = os.path.join(self.get_cog_data_directory(), "map_cache")
        if not os.path.exists(map_cache_dir):
            os.makedirs(map_cache_dir)

        full_path = os.path.join(map_cache_dir, filename)

        if os.path.exists(full_path):
            return full_path

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    f = await aiofiles.open(full_path, mode="wb")
                    await f.write(await resp.read())
                    await f.close()

        return full_path

    @incidents_group.command(
        name="enable", description="Enable Lancaster incidents feed"
    )
    @commands.has_permissions(administrator=True)
    @commands.is_owner()
    async def enable(self, interaction: discord.Interaction):
        channel_id = interaction.channel.id
        incident_config, created = IncidentConfig.get_or_create(
            guild_id=interaction.guild.id,
            channel_id=channel_id,
        )
        incident_config.enabled = True
        incident_config.save()

        await interaction.response.send_message(
            "Incidents feed enabled", ephemeral=True
        )

    @incidents_group.command(name="status", description="Show LCWC cog status")
    async def status(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Status", description="Incident Cog Status", color=0x00FF00
        )
        embed.add_field(
            name="Active Incidents", value=f"{len(self.active_incidents)}", inline=False
        )
        embed.add_field(
            name="Last Updated",
            value=f'{self.last_updated.astimezone(self.est).strftime("%m/%d/%Y, %H:%M:%S") or "Never"}',
            inline=False,
        )
        embed.add_field(
            name="Package Version", value=f"{self.get_lcwc_version()}", inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    lcwc_dist = None

    def get_lcwc_version(self):
        if not self.lcwc_dist:
            self.get_lcwc_dist()
        return self.lcwc_dist.version

    def get_lcwc_dist(self):
        if not self.lcwc_dist:
            self.lcwc_dist = pkg_resources.get_distribution("lcwc")
        return self.lcwc_dist


async def setup(bot):
    await bot.add_cog(Incidents(bot))
