from tortoise import fields
from tortoise.models import Model


class R9KConfig(Model):
    """Per-guild configuration designating a single R9K channel."""

    id = fields.IntField(primary_key=True)
    guild_id = fields.BigIntField(unique=True)
    channel_id = fields.BigIntField(null=True)
    enabled = fields.BooleanField(default=True)
    # Timeout to apply to a user who posts a duplicate, in seconds.
    # 0 (the default) disables the timeout action; the message is still deleted.
    timeout_seconds = fields.IntField(default=0)
    # How long a recorded phrase stays "seen", in seconds. Once a record is
    # older than this it expires and the phrase may be reused.
    # 0 (the default) means history never expires.
    history_ttl_seconds = fields.IntField(default=0)

    class Meta:
        table = "r9k_config"


class R9KMessage(Model):
    """A recorded unique message hash for an R9K channel.

    Uniqueness is scoped per-channel: a phrase is only a duplicate if it was
    previously said in the same channel.
    """

    id = fields.IntField(primary_key=True)
    channel_id = fields.BigIntField()
    content_hash = fields.CharField(max_length=255)
    author_id = fields.BigIntField()
    message_id = fields.BigIntField()
    created_at = fields.DatetimeField()

    class Meta:
        table = "r9k_message"
        # a given normalized phrase may only exist once per channel
        unique_together = (("channel_id", "content_hash"),)
