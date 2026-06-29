import os

from dotenv import load_dotenv
from playhouse.migrate import *

load_dotenv()

db = SqliteDatabase(os.getenv("SQLITE_DB"))

TABLE = "paywall_pattern"


def run():
    existing_tables = db.get_tables()
    if TABLE not in existing_tables:
        db.execute_sql(f"""
            CREATE TABLE {TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id BIGINT NOT NULL,
                pattern VARCHAR(255) NOT NULL
            )
            """)
        db.execute_sql(f"CREATE INDEX idx_{TABLE}_guild_id ON {TABLE} (guild_id)")
        print(f"Created table '{TABLE}'.")
    else:
        print(f"Table '{TABLE}' already exists. No changes made.")
