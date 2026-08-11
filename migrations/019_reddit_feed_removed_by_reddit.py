"""Distinguish posts removed by reddit from posts removed by their author."""

from peewee import BooleanField

from migrations.helpers import MigrationContext


def upgrade(ctx: MigrationContext) -> None:
    ctx.add_columns("reddit_post", removed_by_reddit=BooleanField(default=False))
