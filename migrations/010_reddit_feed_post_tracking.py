"""Track score, comment count and edit state on synced reddit posts."""

from peewee import BooleanField, DateTimeField, IntegerField

from migrations.helpers import MigrationContext


def upgrade(ctx: MigrationContext) -> None:
    ctx.add_columns(
        "reddit_post",
        comment_count=IntegerField(null=True),
        score=IntegerField(null=True),
        deleted=BooleanField(default=False),
        edited=BooleanField(default=False),
        removed=BooleanField(default=False),
        last_updated=DateTimeField(null=True),
        channel_id=IntegerField(null=True),
    )
