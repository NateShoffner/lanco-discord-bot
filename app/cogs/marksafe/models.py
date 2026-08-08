import uuid

from tortoise import fields
from tortoise.models import Model


class MarkSafeUser(Model):
    id = fields.IntField(primary_key=True)
    user_id = fields.IntField()
    guild_id = fields.IntField()
    event_id = fields.UUIDField()
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "mark_safe_user"
        unique_together = (("user_id", "guild_id", "event_id"),)


class MarkSafeEvent(Model):
    id = fields.UUIDField(primary_key=True, default=uuid.uuid4)
    name = fields.TextField()
    description = fields.TextField()
    guild_id = fields.IntField()
    active = fields.BooleanField(default=True)

    class Meta:
        table = "mark_safe_event"


class MarkSafeConfig(Model):
    id = fields.IntField(primary_key=True)
    guild_id = fields.IntField(unique=True)
    enabled = fields.BooleanField(default=False)

    class Meta:
        table = "mark_safe_config"
