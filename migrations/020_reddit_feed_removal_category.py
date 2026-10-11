"""Record the raw removed_by_category alongside the removal booleans."""

from peewee import CharField

from migrations.helpers import MigrationContext


def upgrade(ctx: MigrationContext) -> None:
    ctx.add_columns("reddit_post", removal_category=CharField(null=True))
