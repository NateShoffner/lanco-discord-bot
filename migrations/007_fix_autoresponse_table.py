"""Rename the hyphenated auto-response table to auto_response."""

from migrations.helpers import MigrationContext


def upgrade(ctx: MigrationContext) -> None:
    ctx.rename_table("auto-response", "auto_response")
