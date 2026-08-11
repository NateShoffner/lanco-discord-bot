"""Make the tech lanc post schedule configurable."""

from peewee import IntegerField

from migrations.helpers import MigrationContext


def upgrade(ctx: MigrationContext) -> None:
    ctx.add_columns(
        "tech_lanc_config",
        day_of_week=IntegerField(default=0),
        post_hour=IntegerField(default=8),
        post_minute=IntegerField(default=0),
    )
