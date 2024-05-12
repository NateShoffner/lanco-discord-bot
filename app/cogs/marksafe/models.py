import datetime
import uuid

from db import BaseModel
from peewee import *


class MarkSafeUser(BaseModel):
    user_id = IntegerField()
    guild_id = IntegerField()
    event_id = UUIDField()
    timestamp = DateTimeField(default=datetime.datetime.utcnow())

    class Meta:
        table_name = "mark_safe_user"
        primary_key = CompositeKey("user_id", "guild_id", "event_id")


class MarkSafeEvent(BaseModel):
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    name = TextField()
    description = TextField()
    guild_id = IntegerField()
    active = BooleanField(default=True)

    class Meta:
        table_name = "mark_safe_event"
        composite_key = ("name", "guild_id")


class MarkSafeConfig(BaseModel):
    guild_id = IntegerField(unique=True)
    enabled = BooleanField(default=False)

    class Meta:
        table_name = "mark_safe_config"
