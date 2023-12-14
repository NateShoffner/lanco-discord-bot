from peewee import *

from db import BaseModel


class IncidentConfig(BaseModel):
    guild_id = IntegerField(unique=True)
    enabled = BooleanField(default=False)
    channel_id = IntegerField(null=True)
    last_known_incident = IntegerField(null=True)

    class Meta:
        table_name = "incidents_config"
