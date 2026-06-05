import os

from dotenv import load_dotenv
from playhouse.migrate import *

load_dotenv()

db = SqliteDatabase(os.getenv("SQLITE_DB"))

migrator = SqliteMigrator(db)

table_name = "tech_lanc_guild_config"

new_columns = {
    "ping_role_id": BigIntegerField(null=True),
    "location_name": TextField(default="West Art"),
    "location_url": TextField(
        default="https://www.google.com/maps/search/?api=1&query=West+Art+Lancaster+PA"
    ),
}


def run():
    existing_columns = db.get_columns(table_name)
    for column_name, field in new_columns.items():
        if column_name not in [col.name for col in existing_columns]:
            migrate(migrator.add_column(table_name, column_name, field))
        else:
            print(f"Column '{column_name}' already exists. No changes made.")
