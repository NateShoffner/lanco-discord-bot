# 003_change_tiktokfix_table_name.py

import os

from dotenv import load_dotenv
from playhouse.migrate import *

load_dotenv()

old_table_name = "tiktokfix_config"
new_table_name = "tiktokembed_config"

db = SqliteDatabase(os.getenv("SQLITE_DB"))

migrator = SqliteMigrator(db)

migrate(
    migrator.rename_table(old_table_name, new_table_name),
)
