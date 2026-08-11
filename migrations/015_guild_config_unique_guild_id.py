"""Enforce one config row per guild."""

from migrations.helpers import MigrationContext

TABLE = "guild_configs"


def upgrade(ctx: MigrationContext) -> None:
    if not ctx.table_exists(TABLE):
        return

    # Keep the oldest row for each guild. rowid is SQLite specific, which is
    # the only backend this ran against.
    ctx.execute(
        f"""
        DELETE FROM {TABLE}
        WHERE rowid NOT IN (
            SELECT MIN(rowid) FROM {TABLE} GROUP BY guild_id
        )
    """
    )

    # SQLite cannot ADD CONSTRAINT to an existing table, so uniqueness comes
    # from an index instead.
    ctx.create_index(TABLE, "guild_configs_guild_id", ["guild_id"], unique=True)
