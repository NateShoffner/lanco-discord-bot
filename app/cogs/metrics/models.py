import datetime

from db import BaseModel
from peewee import *


class BotMetrics(BaseModel):
    recorded_at = DateTimeField(default=datetime.datetime.utcnow)
    latency_ms = FloatField()
    guild_count = IntegerField()
    user_count = IntegerField()
    uptime_seconds = FloatField()
    memory_mb = FloatField(null=True)
    cpu_percent = FloatField(null=True)
    cog_count = IntegerField()

    class Meta:
        table_name = "bot_metrics"


class BotGuild(BaseModel):
    guild_id = BigIntegerField(unique=True)
    name = CharField()
    joined_at = DateTimeField(default=datetime.datetime.utcnow)

    class Meta:
        table_name = "bot_guilds"
