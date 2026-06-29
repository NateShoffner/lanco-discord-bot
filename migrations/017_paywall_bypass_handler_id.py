import os

from dotenv import load_dotenv
from playhouse.migrate import *

load_dotenv()

db = SqliteDatabase(os.getenv("SQLITE_DB"))

migrator = SqliteMigrator(db)

TABLE = "paywall_bypass_config"


def run():
    existing_tables = db.get_tables()
    if TABLE not in existing_tables:
        print(f"Table '{TABLE}' does not exist, skipping.")
        return

    existing_columns = [col.name for col in db.get_columns(TABLE)]
    if "handler_id" not in existing_columns:
        migrate(migrator.add_column(TABLE, "handler_id", CharField(default="")))
        print(f"Added 'handler_id' column to {TABLE}.")
    else:
        print(f"Column 'handler_id' already exists in {TABLE}. No changes made.")
