"""Rebuild trending_channel_config around the per-channel trendingchannel model."""

from peewee import BigIntegerField, BooleanField, DateTimeField, Model, TextField

from migrations.helpers import MigrationContext

TABLE = "trending_channel_config"
LEGACY = "trending_channel_config_legacy"


class TrendingChannelConfig(Model):
    """Snapshot of the trendingchannel model as of this migration."""

    guild_id = BigIntegerField()
    channel_id = BigIntegerField()
    enabled_by = BigIntegerField(null=True)
    rename_enabled = BooleanField(default=False)
    last_seen_message_id = BigIntegerField(null=True)
    last_analyzed_message_id = BigIntegerField(null=True)
    last_updated_at = DateTimeField(null=True)
    last_name = TextField(null=True)
    last_topic = TextField(null=True)

    class Meta:
        table_name = TABLE


def upgrade(ctx: MigrationContext) -> None:
    # A fresh database has no table yet; the cog creates it in the new shape.
    # A database that already carries the new columns needs nothing either.
    if not ctx.table_exists(TABLE) or ctx.column_exists(TABLE, "rename_enabled"):
        return

    # The earlier shape was one channel per guild (guild_id UNIQUE) and renaming
    # was the only behaviour. SQLite cannot drop a UNIQUE constraint in place,
    # so rebuild the table and carry the rows over with renaming kept on.
    ctx.rename_table(TABLE, LEGACY)
    ctx.create_table(TrendingChannelConfig)
    ctx.create_index(TABLE, f"{TABLE}_channel_id", ["channel_id"], unique=True)
    ctx.execute(
        f"INSERT INTO {TABLE} (guild_id, channel_id, rename_enabled) "
        f"SELECT guild_id, channel_id, 1 FROM {LEGACY} "
        "WHERE channel_id IS NOT NULL"
    )
    ctx.execute(f"DROP TABLE {LEGACY}")
