# migrate.py

import importlib.util
import os

MIGRATIONS_DIR = "migrations"


def run_migration_script(script_path):
    spec = importlib.util.spec_from_file_location("migration", script_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.run()


def run_migrations():
    migrations = sorted(os.listdir(MIGRATIONS_DIR))
    for migration in migrations:
        if migration.endswith(".py"):
            migration_path = os.path.join(MIGRATIONS_DIR, migration)
            print(f"Running migration: {migration}...", end="")
            run_migration_script(migration_path)
            print(" Done.")


if __name__ == "__main__":
    run_migrations()
