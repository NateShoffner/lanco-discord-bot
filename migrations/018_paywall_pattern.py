"""Add per-guild paywall URL patterns."""

from peewee import AutoField, BigIntegerField, CharField, Model

from migrations.helpers import MigrationContext


class PaywallPattern(Model):
    id = AutoField()
    guild_id = BigIntegerField()
    pattern = CharField()

    class Meta:
        table_name = "paywall_pattern"


def upgrade(ctx: MigrationContext) -> None:
    ctx.create_table(PaywallPattern)
    ctx.create_index("paywall_pattern", "idx_paywall_pattern_guild_id", ["guild_id"])
