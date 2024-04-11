from db import BaseModel
from peewee import *


class IncidentsGlobalConfig(BaseModel):
    name = CharField(unique=True)
    value = CharField()

    class Meta:
        table_name = "incidents_global_config"


class IncidentConfig(BaseModel):
    guild_id = IntegerField(unique=True)
    enabled = BooleanField(default=False)
    channel_id = IntegerField(null=True)
    last_known_incident = IntegerField(null=True)
    latest_incident_timestamp = IntegerField(null=True)  # used for non-arcgis incidents

    class Meta:
        table_name = "incidents_config"
