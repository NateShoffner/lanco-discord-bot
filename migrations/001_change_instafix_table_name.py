"""Rename instafix_config to instaembed_config."""

from migrations.helpers import MigrationContext


def upgrade(ctx: MigrationContext) -> None:
    ctx.rename_table("instafix_config", "instaembed_config")
