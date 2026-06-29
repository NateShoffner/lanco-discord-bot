import os

from dotenv import load_dotenv
from playhouse.migrate import *

load_dotenv()

db = SqliteDatabase(os.getenv("SQLITE_DB"))

migrator = SqliteMigrator(db)

TABLES = [
    "twitterembed_config",
    "instaembed_config",
    "tiktokembed_config",
    "redditembed_config",
    "facebookembed_config",
]


def run():
    existing_tables = db.get_tables()
    for table in TABLES:
        if table not in existing_tables:
            print(f"Table '{table}' does not exist, skipping.")
            continue
        existing_columns = [col.name for col in db.get_columns(table)]
        if "handler_id" not in existing_columns:
            migrate(migrator.add_column(table, "handler_id", CharField(default="")))
            print(f"Added 'handler_id' column to {table}.")
        else:
            print(f"Column 'handler_id' already exists in {table}. No changes made.")
