from tortoise import fields
from tortoise.models import Model


class YoutubeSubscription(Model):
    id = fields.IntField(primary_key=True)
    guild_id = fields.IntField(unique=True)
    channel_id = fields.IntField()
    yt_channel_id = fields.CharField(max_length=255)
    # Prod's column is declared INTEGER and the Peewee model said IntegerField,
    # but the cog has always written an ISO-8601 timestamp string here and
    # compares it as a string. SQLite affinity let that slide; Tortoise's
    # IntField would raise on both read and write of the existing rows, so this
    # is typed as the string it actually holds.
    last_publish = fields.CharField(max_length=255, null=True)

    class Meta:
        table = "youtube_subscriptions"
