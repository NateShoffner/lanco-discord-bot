from tortoise import fields
from tortoise.models import Model


class RSSFeedConfig(Model):
    id = fields.IntField(primary_key=True)
    channel_id = fields.IntField(null=True)
    url = fields.CharField(max_length=255, null=True)
    last_checked = fields.DatetimeField(null=True)

    class Meta:
        table = "rss_feed_config"
        unique_together = (("channel_id", "url"),)
