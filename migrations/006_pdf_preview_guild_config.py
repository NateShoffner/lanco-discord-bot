# 005_custom_commands_channel_id.py

import os

from dotenv import load_dotenv
from playhouse.migrate import *

load_dotenv()

table_name = "pdf_preview_config"

db = SqliteDatabase(os.getenv("SQLITE_DB"))

migrator = SqliteMigrator(db)

migrate(
    migrator.add_column(table_name, "preview_pages", IntegerField(default=1)),
    migrator.add_column(table_name, "virus_check", BooleanField(default=True)),
)
