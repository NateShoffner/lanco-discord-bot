"""Rename twitterfix_config to twitterembed_config."""

from migrations.helpers import MigrationContext


def upgrade(ctx: MigrationContext) -> None:
    ctx.rename_table("twitterfix_config", "twitterembed_config")
