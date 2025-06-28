from db import BaseModel
from peewee import *


class RSSFeedConfig(BaseModel):
    channel_id = IntegerField(null=True)
    url = CharField(null=True)
    last_checked = DateTimeField(null=True)

    class Meta:
        table_name = "rss_feed_config"
        primary_key = CompositeKey("channel_id", "url")
