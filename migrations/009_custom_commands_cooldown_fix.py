"""Make custom command cooldowns nullable.

008 added cooldown as NOT NULL without a DB level default, which makes SQLite
reject INSERTs that do not set the column explicitly.
"""

from peewee import IntegerField

from migrations.helpers import MigrationContext


def upgrade(ctx: MigrationContext) -> None:
    ctx.add_columns("custom_commands", cooldown=IntegerField(default=0, null=True))
    ctx.drop_not_null("custom_commands", "cooldown")
