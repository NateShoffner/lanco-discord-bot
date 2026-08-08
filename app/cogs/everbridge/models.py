from tortoise import fields
from tortoise.models import Model


class EverbridgeConfig(Model):
    id = fields.IntField(primary_key=True)
    channel_id = fields.IntField(null=True)
    last_event_date = fields.DatetimeField(null=True)
    subscription_name = fields.CharField(max_length=255, null=True)

    class Meta:
        table = "everbridge_config"
