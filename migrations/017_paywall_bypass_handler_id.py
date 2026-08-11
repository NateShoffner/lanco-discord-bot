"""Record which handler the paywall bypass config uses."""

from peewee import CharField

from migrations.helpers import MigrationContext


def upgrade(ctx: MigrationContext) -> None:
    ctx.add_columns("paywall_bypass_config", handler_id=CharField(default=""))
