from tortoise import fields
from tortoise.models import Model


class IncidentsGlobalConfig(Model):
    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=255, unique=True)
    value = fields.CharField(max_length=255)

    class Meta:
        table = "incidents_global_config"


class IncidentConfig(Model):
    id = fields.IntField(primary_key=True)
    guild_id = fields.IntField(unique=True)
    enabled = fields.BooleanField(default=False)
    channel_id = fields.IntField(null=True)
    last_known_incident = fields.IntField(null=True)
    latest_incident_timestamp = fields.IntField(
        null=True
    )  # used for non-arcgis incidents

    class Meta:
        table = "incidents_config"
