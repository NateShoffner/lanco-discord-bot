"""Add page count and virus check options to the PDF preview config."""

from peewee import BooleanField, IntegerField

from migrations.helpers import MigrationContext


def upgrade(ctx: MigrationContext) -> None:
    ctx.add_columns(
        "pdf_preview_config",
        preview_pages=IntegerField(default=1),
        virus_check=BooleanField(default=True),
    )
