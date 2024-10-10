from db import BaseModel
from peewee import *


class YoutubeSubscription(BaseModel):
    guild_id = IntegerField(unique=True)
    channel_id = IntegerField()
    yt_channel_id = CharField()
    last_publish = IntegerField(null=True)

    class Meta:
        table_name = "youtube_subscriptions"
