# 009_custom_commands_cooldown_fix.py
# cooldown was added as NOT NULL in 008 without a proper DB-level default,
# which causes SQLite to reject INSERTs that don't explicitly set the column.
# This migration ensures the column exists and is nullable.

import os

from dotenv import load_dotenv
from playhouse.migrate import *

load_dotenv()

table_name = "custom_commands"

db = SqliteDatabase(os.getenv("SQLITE_DB"))

migrator = SqliteMigrator(db)


def run():
    existing_columns = db.get_columns(table_name)
    col_names = [col.name for col in existing_columns]

    if "cooldown" not in col_names:
        migrate(
            migrator.add_column(
                table_name, "cooldown", IntegerField(default=0, null=True)
            )
        )
    else:
        col = next(c for c in existing_columns if c.name == "cooldown")
        if not col.null:
            migrate(migrator.drop_not_null(table_name, "cooldown"))
