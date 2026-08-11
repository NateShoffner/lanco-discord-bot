"""Scope custom commands to a channel."""

from peewee import IntegerField

from migrations.helpers import MigrationContext


def upgrade(ctx: MigrationContext) -> None:
    ctx.add_columns("custom_commands", channel_id=IntegerField(null=True))
