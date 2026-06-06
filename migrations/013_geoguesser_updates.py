import os

from dotenv import load_dotenv
from playhouse.migrate import *

load_dotenv()

db = SqliteDatabase(os.getenv("SQLITE_DB"))

migrator = SqliteMigrator(db)


def run():
    # add label column to geoguesser_locations
    if "geoguesser_locations" in db.get_tables():
        existing_columns = [col.name for col in db.get_columns("geoguesser_locations")]
        if "label" not in existing_columns:
            migrate(
                migrator.add_column(
                    "geoguesser_locations", "label", CharField(null=True)
                )
            )
            print("Added 'label' column to geoguesser_locations.")
        else:
            print("Column 'label' already exists. No changes made.")
    else:
        print("Table 'geoguesser_locations' does not exist. No changes made.")

    # create geoguesser_game_results table
    if "geoguesser_game_results" not in db.get_tables():
        db.execute_sql("""
            CREATE TABLE geoguesser_game_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                mode TEXT NOT NULL,
                score REAL NOT NULL,
                rounds_played INTEGER NOT NULL,
                played_at DATETIME NOT NULL
            )
        """)
        db.execute_sql(
            "CREATE INDEX idx_ggr_guild ON geoguesser_game_results (guild_id)"
        )
        db.execute_sql(
            "CREATE INDEX idx_ggr_user ON geoguesser_game_results (guild_id, user_id)"
        )
        db.execute_sql(
            "CREATE INDEX idx_ggr_played_at ON geoguesser_game_results (played_at)"
        )
        print("Created table 'geoguesser_game_results' with indexes.")
    else:
        print("Table 'geoguesser_game_results' already exists. No changes made.")

    # add scoring_version column if missing
    if "geoguesser_game_results" in db.get_tables():
        existing_columns = [
            col.name for col in db.get_columns("geoguesser_game_results")
        ]
        if "scoring_version" not in existing_columns:
            migrate(
                migrator.add_column(
                    "geoguesser_game_results",
                    "scoring_version",
                    IntegerField(default=1),
                )
            )
            print("Added 'scoring_version' column to geoguesser_game_results.")
        else:
            print("Column 'scoring_version' already exists. No changes made.")
