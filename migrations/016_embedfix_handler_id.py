"""Record which handler each embed fix config uses."""

from peewee import CharField

from migrations.helpers import MigrationContext

TABLES = [
    "twitterembed_config",
    "instaembed_config",
    "tiktokembed_config",
    "redditembed_config",
    "facebookembed_config",
]


def upgrade(ctx: MigrationContext) -> None:
    for table in TABLES:
        ctx.add_columns(table, handler_id=CharField(default=""))
