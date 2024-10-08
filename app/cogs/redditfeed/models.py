from db import BaseModel
from peewee import *


class RedditFeedConfig(BaseModel):
    channel_id = IntegerField(null=True)
    subreddit = CharField(null=True)
    last_known_post_creation = IntegerField(null=True)

    class Meta:
        table_name = "reddit_feed_config"
        primary_key = CompositeKey("channel_id", "subreddit")


class RedditPost(BaseModel):
    post_id = CharField()
    subreddit = CharField()
    title = CharField()
    permalink = CharField()
    created = IntegerField()
    author = CharField()
    is_nsfw = BooleanField()
    spoiler = BooleanField()
    message_id = BigIntegerField()

    class Meta:
        table_name = "reddit_post"
        primary_key = CompositeKey("post_id", "message_id")
