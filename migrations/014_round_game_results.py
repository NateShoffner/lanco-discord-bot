import os

from dotenv import load_dotenv
from playhouse.migrate import *

load_dotenv()

db = SqliteDatabase(os.getenv("SQLITE_DB"))


def run():
    if "round_game_results" not in db.get_tables():
        db.execute_sql("""
            CREATE TABLE round_game_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_name TEXT NOT NULL,
                game_id TEXT NOT NULL,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                mode TEXT NOT NULL,
                score REAL NOT NULL,
                rounds_played INTEGER NOT NULL,
                scoring_version INTEGER NOT NULL,
                played_at DATETIME NOT NULL
            )
            """)
        db.execute_sql(
            "CREATE INDEX idx_rgr_game_guild_user ON round_game_results (game_name, guild_id, user_id)"
        )
        db.execute_sql(
            "CREATE INDEX idx_rgr_game_id ON round_game_results (game_name, game_id)"
        )
        print("Created table 'round_game_results' with indexes.")
    else:
        print("Table 'round_game_results' already exists. No changes made.")
