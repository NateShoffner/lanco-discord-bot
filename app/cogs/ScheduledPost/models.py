import uuid

from db import BaseModel
from peewee import *


class ScheduledPost(BaseModel):
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    guild_id = BigIntegerField()
    channel_id = BigIntegerField()
    created_by = BigIntegerField()
    message = TextField(null=True)
    embed_title = TextField(null=True)
    embed_description = TextField(null=True)
    embed_color = IntegerField(null=True)
    role_ping_id = BigIntegerField(null=True)
    cron_expression = TextField()  # e.g. "0 9 * * 1" for every Monday at 9am
    next_run_at = DateTimeField()
    last_run_at = DateTimeField(null=True)
    is_recurring = BooleanField(default=True)
    is_active = BooleanField(default=True)

    class Meta:
        table_name = "scheduled_posts"
