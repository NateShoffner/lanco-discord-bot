import datetime
import os
from dataclasses import dataclass
from urllib.parse import urlencode

import aiofiles
import aiohttp
import discord
import googlemaps
import pkg_resources
import pytz
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Select, View
from lcwc.arcgis import ArcGISClient, ArcGISIncident
from lcwc.category import IncidentCategory
from lcwc.client import Client
from lcwc.feed import FeedClient
from lcwc.incident import Incident
from lcwc.web import WebClient
from utils.command_utils import is_bot_owner, is_bot_owner_or_admin

from .geocoder import IncidentGeocoder
from .models import IncidentConfig, IncidentsGlobalConfig


@dataclass
class IncidentFeedOption:
    client: Client
    name: str
    icon: str
    description: str


class Incidents(LancoCog):
    incidents_group = app_commands.Group(
        name="incidents", description="Incident commands"
    )

    est = pytz.timezone("US/Eastern")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot.database.create_tables([IncidentsGlobalConfig, IncidentConfig])

        gmaps = googlemaps.Client(key=os.getenv("GMAPS_API_KEY"))
        self.geocoder = IncidentGeocoder(gmaps)

        self.arcgis_client = ArcGISClient()
        self.feed_client = FeedClient()
        self.web_client = WebClient()
        self.clients = [
            self.arcgis_client,
            self.feed_client,
            self.web_client,
        ]

        client_config = IncidentsGlobalConfig.get_or_none(
            IncidentsGlobalConfig.name == "client"
        )
        if client_config:
            self.logger.info(f"Found global config: {client_config.value}")
            self.set_client_from_name(client_config.value)
        else:
            self.current_client = self.arcgis_client

        self.active_incidents = []
        self.last_sync_attempt = None
        self.last_successful_sync = None

    @commands.Cog.listener()
    async def on_ready(self):
        await super().on_ready()
        self.get_incidents.change_interval(seconds=5)
        self.get_incidents.start()

    @tasks.loop(seconds=10)
    async def get_incidents(self):
        self.logger.info(f"Getting incidents via {self.current_client.name}")
        async with aiohttp.ClientSession() as session:
            try:
                self.last_sync_attempt = datetime.datetime.now()
                if isinstance(self.current_client, ArcGISClient):
                    incidents = await self.current_client.get_incidents(
                        session, throw_on_error=True
                    )
                else:
                    incidents = await self.current_client.get_incidents(session)
                self.last_successful_sync = datetime.datetime.now()
            except Exception as e:
                self.logger.error(f"Error getting incidents: {e}")
                return

            for incident in incidents:
                subbed_guilds = IncidentConfig.select().where(
                    IncidentConfig.enabled == True
                )

                for guild in subbed_guilds:
                    if isinstance(self.current_client, ArcGISClient):
                        # TODO shouldn't need to do this after upstream fix is applied fix out of order incidents
                        if (
                            guild.last_known_incident
                            and guild.last_known_incident >= incident.number
                        ):
                            continue

                        self.logger.info(
                            f"New incident: {incident.number} for {guild.guild_id}"
                        )

                        guild.last_known_incident = incident.number
                        guild.save()

                    else:
                        # convert the incident date to a timestamp
                        incident_timestamp = incident.date.timestamp()

                        if (
                            guild.latest_incident_timestamp
                            and guild.latest_incident_timestamp >= incident_timestamp
                        ):
                            continue

                        self.logger.info(
                            f"New incident: {incident.description} for {guild.guild_id}"
                        )

                        guild.latest_incident_timestamp = incident_timestamp
                        guild.save()

                    # TODO possible edge case where this embed fails but the incident was logged in the db already (due to having to support multiple clients)
                    embed, map_attachment = await self.build_incident_embed(incident)
                    message = await self.bot.get_channel(guild.channel_id).send(
                        file=map_attachment, embed=embed
                    )

            self.active_incidents = incidents

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

        if isinstance(incident, ArcGISIncident):
            maps_url = f"https://www.google.com/maps/search/?api=1&query={incident.coordinates.latitude},{incident.coordinates.longitude}"
        else:
            coords = self.geocoder.get_coordinates(incident)
            if not coords:
                return None
            lat, lng = coords
            maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"

        incident_time = incident.date.astimezone(self.est)

        embed = discord.Embed(
            title=f"{emoji_map[incident.category]} Active {str(incident.category.value)} Incident",
            color=color_map[incident.category],
            url=maps_url,
            timestamp=incident_time,
        )

        full_location = f"{incident.municipality}"
        if incident.intersection:
            full_location = f"{incident.intersection}\n{full_location}"

        embed.add_field(name="Location", value=f"{full_location}", inline=False)
        embed.add_field(
            name="Description", value=f"{incident.description}", inline=False
        )

        if isinstance(incident, ArcGISIncident):
            embed.add_field(name="Agency", value=f"{incident.agency}", inline=False)

        embed.add_field(
            name="Units Assigned",
            value=(
                "None"
                if len(incident.units) == 0
                else "\n".join([unit.full_name for unit in incident.units])
            ),
            inline=True,
        )

        if isinstance(incident, ArcGISIncident):
            embed.set_footer(text=f"#{incident.number} • Priority: {incident.priority}")

        embed.set_image(url="attachment://map.png")

        return (embed, map_attachment)

    async def get_map(self, incident: Incident) -> None:
        """Downloads the map image for the given incident and caches it."""

        map_width = 400
        map_height = 300

        if isinstance(incident, ArcGISIncident):
            lat = incident.coordinates.latitude
            lng = incident.coordinates.longitude
        else:
            coords = self.geocoder.get_coordinates(incident)
            if not coords:
                return None
            lat, lng = coords

        url_params = {
            "center": f"{lat},{lng}",
            "zoom": 15,
            "scale": "1",
            "size": f"{map_width}x{map_height}",
            "type": "roadmap",
            "format": "png",
            "key": os.getenv("GMAPS_API_KEY"),
            "markers": f"{lat},{lng}",
        }

        url = f"https://maps.googleapis.com/maps/api/staticmap?{urlencode(url_params)}"

        if isinstance(incident, ArcGISIncident):
            filename = f"{incident.number}.png"
        else:
            filename = f"ts_{incident.date.timestamp()}.png"

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
    @is_bot_owner_or_admin()
    async def enable(self, interaction: discord.Interaction):
        incident_config, created = IncidentConfig.get_or_create(
            guild_id=interaction.guild.id
        )
        incident_config.channel_id = interaction.channel.id
        incident_config.enabled = True
        incident_config.save()

        await interaction.response.send_message("Incidents feed enabled")

    @incidents_group.command(
        name="disable", description="Disable Lancaster incidents feed"
    )
    @is_bot_owner_or_admin()
    async def disable(self, interaction: discord.Interaction):
        incident_config, created = IncidentConfig.get_or_create(
            guild_id=interaction.guild.id
        )
        incident_config.enabled = False
        incident_config.save()

        await interaction.response.send_message("Incidents feed disabled")

    @incidents_group.command(name="status", description="Show LCWC cog status")
    async def status(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Status", description="Incident Cog Status", color=0x00FF00
        )
        embed.add_field(
            name="Current Client", value=f"{self.current_client.__class__.__name__}"
        )
        embed.add_field(
            name="Active Incidents", value=f"{len(self.active_incidents)}", inline=False
        )
        embed.add_field(
            name="Last Sync Attempt",
            value=f'{self.last_sync_attempt.astimezone(self.est).strftime("%m/%d/%Y, %H:%M:%S") if self.last_sync_attempt else  "Never"}',
            inline=False,
        )
        embed.add_field(
            name="Last Successful Sync",
            value=f'{self.last_successful_sync.astimezone(self.est).strftime("%m/%d/%Y, %H:%M:%S") if self.last_successful_sync else "Never"}',
            inline=False,
        )
        embed.add_field(
            name="Package Version", value=f"{self.get_lcwc_version()}", inline=False
        )

        await interaction.response.send_message(embed=embed)

    @incidents_group.command(name="view", description="View incident details")
    async def view(self, interaction: discord.Interaction, incident_number: int):
        if not isinstance(self.current_client, ArcGISClient):
            await interaction.response.send_message(
                "This command is only available when using the ArcGIS client"
            )
            return

        incident = next(
            (i for i in self.active_incidents if i.number == incident_number), None
        )

        if not incident:
            await interaction.response.send_message(
                f"Could not find incident #{incident_number} in the active incidents list"
            )
            return

        embed, map_attachment = await self.build_incident_embed(incident)
        await interaction.response.send_message(file=map_attachment, embed=embed)

    lcwc_dist = None

    def get_lcwc_version(self):
        if not self.lcwc_dist:
            self.get_lcwc_dist()
        return self.lcwc_dist.version

    def get_lcwc_dist(self):
        if not self.lcwc_dist:
            self.lcwc_dist = pkg_resources.get_distribution("lcwc")
        return self.lcwc_dist

    def set_client_from_name(self, name: str):
        client = next((c for c in self.clients if c.name == name), None)
        if not client:
            self.logger.error(f"Could not find client with name: {name}")
            return
        self.current_client = client
        self.active_incidents = []  # clear out the active incidents list

    async def callback(self, interaction: discord.Interaction):
        client_value = interaction.data["values"][0]
        self.logger.info(f"Setting client to: {client_value}")
        self.set_client_from_name(client_value)

        config, created = IncidentsGlobalConfig.get_or_create(
            name="client", defaults={"value": client_value}
        )
        config.value = client_value
        config.save()

        await interaction.channel.typing()
        await interaction.response.send_message(f"Client set to: {client_value}")

    # TODO make this configurable per server?
    @incidents_group.command(name="setclient", description="Set incident client")
    @is_bot_owner()
    async def setclient(self, interaction: discord.Interaction):
        client_options = [
            IncidentFeedOption(
                self.arcgis_client,
                self.arcgis_client.name,
                "🗺️",
                "ArcGIS Feed",
            ),
            IncidentFeedOption(
                self.feed_client,
                self.feed_client.name,
                "📰",
                "RSS Feed",
            ),
            IncidentFeedOption(
                self.web_client,
                self.web_client.name,
                "🌐",
                "Web Feed",
            ),
        ]

        options = []
        for c in client_options:
            options.append(
                discord.SelectOption(
                    label=f"{c.name} ({c.description})", emoji=c.icon, value=c.name
                )
            )

        select = Select(placeholder="Choose a Client", options=options)
        select.callback = self.callback

        view = View()
        view.add_item(select)

        await interaction.channel.typing()
        await interaction.response.send_message(view=view)


async def setup(bot):
    await bot.add_cog(Incidents(bot))
