"""Add a per-guild command prefix."""

from peewee import CharField

from migrations.helpers import MigrationContext


def upgrade(ctx: MigrationContext) -> None:
    ctx.add_columns("guild_configs", prefix=CharField(default="."))
