from tortoise import fields
from tortoise.models import Model


class RedditFeedConfig(Model):
    id = fields.IntField(primary_key=True)
    channel_id = fields.IntField(null=True)
    subreddit = fields.CharField(max_length=255, null=True)
    last_known_post_creation = fields.IntField(null=True)

    class Meta:
        table = "reddit_feed_config"
        unique_together = (("channel_id", "subreddit"),)


class RedditPost(Model):
    id = fields.IntField(primary_key=True)
    post_id = fields.CharField(max_length=255)
    subreddit = fields.CharField(max_length=255)
    channel_id = fields.BigIntField(null=True)
    title = fields.CharField(max_length=255)
    permalink = fields.CharField(max_length=255)
    created = fields.IntField()
    author = fields.CharField(max_length=255)
    is_nsfw = fields.BooleanField()
    spoiler = fields.BooleanField()
    deleted = fields.BooleanField(default=False)
    removed = fields.BooleanField(default=False)
    removed_by_reddit = fields.BooleanField(default=False)
    edited = fields.BooleanField(default=False)
    comment_count = fields.IntField(null=True)
    score = fields.IntField(null=True)
    last_updated = fields.DatetimeField(null=True)
    message_id = fields.BigIntField()

    class Meta:
        table = "reddit_post"
        # one row per (post, Discord message), so the same post shared to two
        # channels is two rows
        unique_together = (("post_id", "message_id"),)
