# 006_pdf_preview_guild_config.py

import os

from dotenv import load_dotenv
from playhouse.migrate import *

load_dotenv()

table_name = "pdf_preview_config"

db = SqliteDatabase(os.getenv("SQLITE_DB"))

migrator = SqliteMigrator(db)

new_columns = {
    "preview_pages": IntegerField(default=1),
    "virus_check": BooleanField(default=True),
}


def run():
    existing_columns = db.get_columns(table_name)
    for column_name, field in new_columns.items():
        if column_name not in [col.name for col in existing_columns]:
            migrate(migrator.add_column(table_name, column_name, field))
        else:
            print(f"Column '{column_name}' already exists. No changes made.")
