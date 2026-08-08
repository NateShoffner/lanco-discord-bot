from tortoise import fields
from tortoise.models import Model


class TechLancConfig(Model):
    id = fields.IntField(primary_key=True)
    guild_id = fields.BigIntField()
    channel_id = fields.BigIntField()
    day_of_week = fields.IntField(default=0)  # 0=Monday, 6=Sunday
    post_hour = fields.IntField(default=8)  # 0-23 UTC
    post_minute = fields.IntField(default=0)  # 0-59

    class Meta:
        table = "tech_lanc_config"


class TechLancGuildConfig(Model):
    id = fields.IntField(primary_key=True)
    guild_id = fields.BigIntField(unique=True)
    discord_event_url = fields.TextField(null=True)
    ping_role_id = fields.BigIntField(null=True)
    location_name = fields.TextField(default="West Art")
    location_url = fields.TextField(
        default="https://www.google.com/maps/search/?api=1&query=West+Art+Lancaster+PA"
    )

    class Meta:
        table = "tech_lanc_guild_config"


class TechLancAllowedPoster(Model):
    id = fields.IntField(primary_key=True)
    guild_id = fields.BigIntField()
    # Either user_id or role_id will be set, not both
    user_id = fields.BigIntField(null=True)
    role_id = fields.BigIntField(null=True)

    class Meta:
        table = "tech_lanc_allowed_poster"
