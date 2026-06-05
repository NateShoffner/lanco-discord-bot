import os

from dotenv import load_dotenv
from playhouse.migrate import *

load_dotenv()

db = SqliteDatabase(os.getenv("SQLITE_DB"))

migrator = SqliteMigrator(db)

table_name = "tech_lanc_config"

new_columns = {
    "day_of_week": IntegerField(default=0),
    "post_hour": IntegerField(default=8),
    "post_minute": IntegerField(default=0),
}


def run():
    if table_name not in db.get_tables():
        print(f"Table '{table_name}' does not exist. No changes made.")
        return
    existing_columns = db.get_columns(table_name)
    for column_name, field in new_columns.items():
        if column_name not in [col.name for col in existing_columns]:
            migrate(migrator.add_column(table_name, column_name, field))
        else:
            print(f"Column '{column_name}' already exists. No changes made.")
