"""Add authorship, cooldown and AI metadata to custom commands."""

from peewee import BigIntegerField, CharField, DateTimeField, IntegerField

from migrations.helpers import MigrationContext


def upgrade(ctx: MigrationContext) -> None:
    ctx.add_columns(
        "custom_commands",
        command_type=CharField(default="basic", null=False),
        last_updated=DateTimeField(null=True),
        author=BigIntegerField(null=True),
        cooldown=IntegerField(default=0),
        last_used=DateTimeField(null=True),
        owner=BigIntegerField(null=True),
    )

    # AI commands have no static response text
    ctx.drop_not_null("custom_commands", "command_response")
