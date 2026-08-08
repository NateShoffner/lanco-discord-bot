import uuid

from tortoise import fields
from tortoise.models import Model


class ScheduledPost(Model):
    id = fields.UUIDField(primary_key=True, default=uuid.uuid4)
    guild_id = fields.BigIntField()
    channel_id = fields.BigIntField()
    created_by = fields.BigIntField()
    message = fields.TextField(null=True)
    embed_title = fields.TextField(null=True)
    embed_description = fields.TextField(null=True)
    embed_color = fields.IntField(null=True)
    role_ping_id = fields.BigIntField(null=True)
    cron_expression = fields.TextField()  # e.g. "0 9 * * 1" for every Monday at 9am
    next_run_at = fields.DatetimeField()
    last_run_at = fields.DatetimeField(null=True)
    is_recurring = fields.BooleanField(default=True)
    is_active = fields.BooleanField(default=True)

    class Meta:
        table = "scheduled_posts"
