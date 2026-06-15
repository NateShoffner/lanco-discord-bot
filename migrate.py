# migrate.py

import datetime
import importlib.util
import os

from dotenv import load_dotenv
from peewee import *

load_dotenv()

MIGRATIONS_DIR = "migrations"

_db_path = os.getenv("SQLITE_DB", "data/lancobot.db")
_db = SqliteDatabase(_db_path)


class SchemaMigration(Model):
    name = CharField(unique=True)
    applied_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        database = _db
        table_name = "schema_migrations"


def _ensure_tracking_table():
    _db.connect(reuse_if_open=True)
    _db.create_tables([SchemaMigration], safe=True)


def _applied_migrations() -> set:
    return {row.name for row in SchemaMigration.select()}


def _run_migration_script(script_path):
    spec = importlib.util.spec_from_file_location("migration", script_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.run()


def run_migrations():
    _ensure_tracking_table()
    applied = _applied_migrations()

    migrations = sorted(f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".py"))

    for migration in migrations:
        if migration in applied:
            print(f"Skipping {migration} (already applied)")
            continue

        migration_path = os.path.join(MIGRATIONS_DIR, migration)
        print(f"Running migration: {migration}...", end="", flush=True)
        _run_migration_script(migration_path)
        SchemaMigration.create(name=migration)
        print(" Done.")


if __name__ == "__main__":
    run_migrations()
