from db import BaseModel
from peewee import *


class TechLancConfig(BaseModel):
    guild_id = BigIntegerField()
    channel_id = BigIntegerField()
    day_of_week = IntegerField(default=0)  # 0=Monday, 6=Sunday
    post_hour = IntegerField(default=8)  # 0-23 UTC
    post_minute = IntegerField(default=0)  # 0-59

    class Meta:
        table_name = "tech_lanc_config"


class TechLancGuildConfig(BaseModel):
    guild_id = BigIntegerField(unique=True)
    discord_event_url = TextField(null=True)
    ping_role_id = BigIntegerField(null=True)
    location_name = TextField(default="West Art")
    location_url = TextField(
        default="https://www.google.com/maps/search/?api=1&query=West+Art+Lancaster+PA"
    )

    class Meta:
        table_name = "tech_lanc_guild_config"


class TechLancAllowedPoster(BaseModel):
    guild_id = BigIntegerField()
    # Either user_id or role_id will be set, not both
    user_id = BigIntegerField(null=True)
    role_id = BigIntegerField(null=True)

    class Meta:
        table_name = "tech_lanc_allowed_poster"
