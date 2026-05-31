import uuid

from db import BaseModel
from peewee import *


class Reminder(BaseModel):
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = BigIntegerField()
    channel_id = BigIntegerField()
    guild_id = BigIntegerField()
    set_at = DateTimeField()
    due_at = DateTimeField()
    message = TextField()
    issued = BooleanField(default=False)

    class Meta:
        table_name = "user_reminders"
