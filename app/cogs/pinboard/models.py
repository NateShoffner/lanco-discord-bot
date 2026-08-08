from tortoise import fields
from tortoise.models import Model


class PinboardPost(Model):
    id = fields.IntField(primary_key=True)
    pin_owner_id = fields.BigIntField()
    author_id = fields.BigIntField()
    guild_id = fields.BigIntField()
    message_id = fields.BigIntField()
    channel_id = fields.BigIntField()
    created_at = fields.DatetimeField()
    pinned_at = fields.DatetimeField()

    class Meta:
        table = "pinboard_posts"
        unique_together = (("pin_owner_id", "message_id"),)
