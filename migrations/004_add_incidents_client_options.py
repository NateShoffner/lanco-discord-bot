# 004_add_incidents_client_options.py

import os

from dotenv import load_dotenv
from playhouse.migrate import *

load_dotenv()

table_name = "incidents_config"

db = SqliteDatabase(os.getenv("SQLITE_DB"))

migrator = SqliteMigrator(db)

migrate(
    migrator.add_column(
        table_name, "latest_incident_timestamp", IntegerField(null=True)
    ),
)
