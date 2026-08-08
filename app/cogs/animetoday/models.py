from tortoise import fields
from tortoise.models import Model


class AnimeTodayConfig(Model):
    id = fields.IntField(primary_key=True)
    guild_id = fields.IntField()
    channel_id = fields.IntField(null=True)

    class Meta:
        table = "anime_today_config"
