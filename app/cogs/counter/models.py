from tortoise import fields
from tortoise.models import Model


class CounterConfig(Model):
    id = fields.IntField(primary_key=True)
    guild_id = fields.BigIntField(unique=True)
    channel_id = fields.BigIntField(null=True)
    current_count = fields.IntField(default=0)
    last_user_id = fields.BigIntField(null=True)
    high_score = fields.IntField(default=0)

    class Meta:
        table = "counter_config"
