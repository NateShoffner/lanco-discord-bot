# 004_add_incidents_client_options.py

import os

from dotenv import load_dotenv
from playhouse.migrate import *

load_dotenv()

table_name = "incidents_config"

db = SqliteDatabase(os.getenv("SQLITE_DB"))

migrator = SqliteMigrator(db)

new_columns = {
    "latest_incident_timestamp": IntegerField(null=True),
}


def run():
    existing_columns = db.get_columns(table_name)
    for column_name, field in new_columns.items():
        if column_name not in [col.name for col in existing_columns]:
            migrator.add_column(table_name, column_name, field)
        else:
            print(f"Column '{column_name}' already exists. No changes made.")
