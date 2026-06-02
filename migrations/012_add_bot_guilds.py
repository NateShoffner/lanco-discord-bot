import os

from dotenv import load_dotenv
from peewee import *
from playhouse.migrate import *

load_dotenv()

db = SqliteDatabase(os.getenv("SQLITE_DB"))


def run():
    if "bot_guilds" not in db.get_tables():
        db.connect(reuse_if_open=True)
        db.execute_sql("""
            CREATE TABLE bot_guilds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id BIGINT NOT NULL UNIQUE,
                name VARCHAR(255) NOT NULL,
                joined_at DATETIME NOT NULL
            )
        """)
        print("Created bot_guilds table.")
    else:
        print("bot_guilds table already exists. Skipping.")
