"""Track the latest incident timestamp per guild."""

from peewee import IntegerField

from migrations.helpers import MigrationContext


def upgrade(ctx: MigrationContext) -> None:
    ctx.add_columns(
        "incidents_config",
        latest_incident_timestamp=IntegerField(null=True),
    )
