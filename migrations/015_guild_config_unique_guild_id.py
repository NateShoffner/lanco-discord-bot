import os

from dotenv import load_dotenv
from peewee import *

load_dotenv()

db = SqliteDatabase(os.getenv("SQLITE_DB"))

TABLE = "guild_configs"


def run():
    db.connect(reuse_if_open=True)

    if TABLE not in db.get_tables():
        print(f"Table '{TABLE}' does not exist. No changes made.")
        return

    # Deduplicate: keep the row with the lowest rowid for each guild_id.
    db.execute_sql(f"""
        DELETE FROM {TABLE}
        WHERE rowid NOT IN (
            SELECT MIN(rowid) FROM {TABLE} GROUP BY guild_id
        )
    """)

    # SQLite doesn't support ADD CONSTRAINT on existing tables, so we
    # recreate the table with a unique index on guild_id instead.
    indexes = db.get_indexes(TABLE)
    index_names = [idx.name for idx in indexes]
    if "guild_configs_guild_id" not in index_names:
        db.execute_sql(
            f"CREATE UNIQUE INDEX guild_configs_guild_id ON {TABLE} (guild_id)"
        )
        print(f"Added unique index on {TABLE}.guild_id")
    else:
        print("Unique index on guild_id already exists. No changes made.")
