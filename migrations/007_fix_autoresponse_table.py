# 007_fix_autoresponse_table.py

import os

from dotenv import load_dotenv
from playhouse.migrate import *

load_dotenv()

old_table_name = "auto-response"
new_table_name = "auto_response"

db = SqliteDatabase(os.getenv("SQLITE_DB"))

migrator = SqliteMigrator(db)


def run():
    # check if the old and new tables exists
    if old_table_name in db.get_tables() and new_table_name not in db.get_tables():
        migrate(
            migrator.rename_table(old_table_name, new_table_name),
        )
    else:
        print(f"Table '{old_table_name}' does not exist. No changes made.")
