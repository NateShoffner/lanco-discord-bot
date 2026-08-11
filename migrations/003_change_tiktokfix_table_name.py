"""Rename tiktokfix_config to tiktokembed_config."""

from migrations.helpers import MigrationContext


def upgrade(ctx: MigrationContext) -> None:
    ctx.rename_table("tiktokfix_config", "tiktokembed_config")
