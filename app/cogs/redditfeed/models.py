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
    channel_id = BigIntegerField(null=True)
    title = CharField()
    permalink = CharField()
    created = IntegerField()
    author = CharField()
    is_nsfw = BooleanField()
    spoiler = BooleanField()
    deleted = BooleanField(default=False)
    removed = BooleanField(default=False)
    removed_by_reddit = BooleanField(default=False)
    # Raw removed_by_category, so a value we do not classify yet is still
    # visible when working out why an embed says what it says
    removal_category = CharField(null=True)
    edited = BooleanField(default=False)
    comment_count = IntegerField(null=True)
    score = IntegerField(null=True)
    last_updated = DateTimeField(null=True)
    message_id = BigIntegerField()

    class Meta:
        table_name = "reddit_post"
        primary_key = CompositeKey("post_id", "message_id")
