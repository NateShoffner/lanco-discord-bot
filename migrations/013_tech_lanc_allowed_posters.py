import os

from dotenv import load_dotenv
from playhouse.migrate import *

load_dotenv()

db = SqliteDatabase(os.getenv("SQLITE_DB"))


def run():
    db.execute_sql("""
        CREATE TABLE IF NOT EXISTS tech_lanc_allowed_poster (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id BIGINT NOT NULL,
            user_id BIGINT,
            role_id BIGINT
        )
    """)
    print("Created tech_lanc_allowed_poster table (if not exists).")
