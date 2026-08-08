import uuid

from tortoise import fields
from tortoise.models import Model


class Reminder(Model):
    id = fields.UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = fields.BigIntField()
    channel_id = fields.BigIntField()
    guild_id = fields.BigIntField()
    set_at = fields.DatetimeField()
    due_at = fields.DatetimeField()
    message = fields.TextField()
    issued = fields.BooleanField(default=False)

    class Meta:
        table = "user_reminders"
