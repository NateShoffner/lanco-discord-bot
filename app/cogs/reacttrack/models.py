from tortoise import fields
from tortoise.models import Model


class ReactEvent(Model):
    id = fields.IntField(primary_key=True)
    message_id = fields.IntField()
    channel_id = fields.IntField()
    guild_id = fields.IntField()
    user_id = fields.IntField()
    emoji = fields.CharField(max_length=255)
    timestamp = fields.DatetimeField()
    added = fields.BooleanField()

    class Meta:
        table = "react_events"
