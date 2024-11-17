from email import message

from db import BaseModel
from peewee import *


class PinboardPost(BaseModel):
    pin_owner_id = BigIntegerField()
    author_id = BigIntegerField()
    guild_id = BigIntegerField()
    message_id = BigIntegerField()
    channel_id = BigIntegerField()
    created_at = DateTimeField()
    pinned_at = DateTimeField()

    class Meta:
        table_name = "pinboard_posts"
        primary_key = CompositeKey("pin_owner_id", "message_id")
