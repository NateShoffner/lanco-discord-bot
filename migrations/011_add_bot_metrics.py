import os

from dotenv import load_dotenv
from peewee import *
from playhouse.migrate import *

load_dotenv()

db = SqliteDatabase(os.getenv("SQLITE_DB"))


def run():
    if "bot_metrics" not in db.get_tables():
        db.connect(reuse_if_open=True)
        db.execute_sql("""
            CREATE TABLE bot_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at DATETIME NOT NULL,
                latency_ms REAL NOT NULL,
                guild_count INTEGER NOT NULL,
                user_count INTEGER NOT NULL,
                uptime_seconds REAL NOT NULL,
                memory_mb REAL,
                cpu_percent REAL,
                cog_count INTEGER NOT NULL
            )
        """)
        print("Created bot_metrics table.")
    else:
        print("bot_metrics table already exists. Skipping.")
