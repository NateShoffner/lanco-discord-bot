from db import BaseModel
from peewee import *


class R9KConfig(BaseModel):
    """Per-guild configuration designating a single R9K channel."""

    guild_id = BigIntegerField(unique=True)
    channel_id = BigIntegerField(null=True)
    enabled = BooleanField(default=True)
    # Timeout to apply to a user who posts a duplicate, in seconds.
    # 0 (the default) disables the timeout action; the message is still deleted.
    timeout_seconds = IntegerField(default=0)
    # How long a recorded phrase stays "seen", in seconds. Once a record is
    # older than this it expires and the phrase may be reused.
    # 0 (the default) means history never expires.
    history_ttl_seconds = IntegerField(default=0)

    class Meta:
        table_name = "r9k_config"


class R9KMessage(BaseModel):
    """A recorded unique message hash for an R9K channel.

    Uniqueness is scoped per-channel: a phrase is only a duplicate if it was
    previously said in the same channel.
    """

    channel_id = BigIntegerField()
    content_hash = CharField()
    author_id = BigIntegerField()
    message_id = BigIntegerField()
    created_at = DateTimeField()

    class Meta:
        table_name = "r9k_message"
        indexes = (
            # a given normalized phrase may only exist once per channel
            (("channel_id", "content_hash"), True),
        )
