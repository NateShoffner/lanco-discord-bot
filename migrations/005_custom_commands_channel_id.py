# 005_custom_commands_channel_id.py

import os

from dotenv import load_dotenv
from playhouse.migrate import *

load_dotenv()

table_name = "custom_commands"

db = SqliteDatabase(os.getenv("SQLITE_DB"))

migrator = SqliteMigrator(db)

migrate(
    migrator.add_column(table_name, "channel_id", IntegerField(null=True)),
)
