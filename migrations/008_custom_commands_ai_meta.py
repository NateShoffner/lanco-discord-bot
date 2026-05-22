# 008_custom_commands_ai_meta.py

import os

from dotenv import load_dotenv
from playhouse.migrate import *

load_dotenv()

table_name = "custom_commands"

db = SqliteDatabase(os.getenv("SQLITE_DB"))

migrator = SqliteMigrator(db)


def run():
    new_columns = {
        "command_type": CharField(default="basic", null=False),
        "last_updated": DateTimeField(null=True),
        "author": BigIntegerField(null=True),
        "cooldown": IntegerField(default=0),
        "last_used": DateTimeField(null=True),
        "owner": BigIntegerField(null=True),
    }

    updated_columns = {
        "command_response": CharField(null=True),
    }

    existing_columns = db.get_columns(table_name)
    for column_name, field in new_columns.items():
        if column_name not in [col.name for col in existing_columns]:
            migrate(migrator.add_column(table_name, column_name, field))
        else:
            print(f"Column '{column_name}' already exists. No changes made.")

    for column_name, field in updated_columns.items():
        for col in existing_columns:
            if col.name == column_name:
                if not col.null and isinstance(field, CharField) and field.null:
                    migrate(migrator.drop_not_null(table_name, column_name))
                    print(f"Column '{column_name}' altered to allow NULL values.")
                else:
                    print(
                        f"Column '{column_name}' already has the desired properties. No changes made."
                    )
                break
