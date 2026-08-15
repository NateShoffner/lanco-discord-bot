"""Applies pending migrations from ``migrations/``.

Each migration runs exactly once. Applied names are recorded in the
``schema_migrations`` table, and the schema change plus that bookkeeping row
share a transaction, so a failed migration leaves nothing behind and is
retried on the next run, since SQLite makes DDL transactional.

Usage:
    python migrate.py             apply pending migrations
    python migrate.py --status    list applied and pending migrations
"""

import argparse
import datetime
import importlib.util
import logging
import os
import re
import sys

from peewee import CharField, DateTimeField, Model, SqliteDatabase

ROOT = os.path.dirname(os.path.abspath(__file__))

# Migrations import migrations.helpers by name, so the project root has to be
# importable no matter which directory this was invoked from. app/ goes on the
# path for the same reason app/run.py puts it there: its modules import each
# other by bare name.
for _path in (ROOT, os.path.join(ROOT, "app")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from utils.db_backup import prune, snapshot  # noqa: E402

from migrations.helpers import MigrationContext, create_database  # noqa: E402

MIGRATIONS_DIR = os.path.join(ROOT, "migrations")
MIGRATION_PATTERN = re.compile(r"^\d{3}_\w+\.py$")
BACKUP_SUBDIR = "pre_migration"

logger = logging.getLogger("migrate")


class SchemaMigration(Model):
    name = CharField(unique=True)
    applied_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "schema_migrations"


def _discover() -> list:
    """Return migration filenames in the order they must be applied."""
    return sorted(f for f in os.listdir(MIGRATIONS_DIR) if MIGRATION_PATTERN.match(f))


def _load(filename: str):
    path = os.path.join(MIGRATIONS_DIR, filename)
    module_name = f"migrations.{filename[:-3]}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    if not hasattr(module, "upgrade"):
        raise AttributeError(f"{filename} does not define an upgrade(ctx) function")
    return module


def _summary(module) -> str:
    """First line of the migration's docstring, for log output."""
    doc = (module.__doc__ or "").strip().splitlines()
    return f": {doc[0]}" if doc else ""


def _backup(db) -> None:
    """Snapshot the database before anything is applied.

    Migrations run unattended on every deploy and some of them delete rows, so
    a run that is about to change something takes a restore point first. A
    failure here aborts the run: the whole point is not to migrate without one.
    Set DATABASE_BACKUP_DIRECTORY empty to opt out, as DatabaseBackup does.
    """
    if not isinstance(db, SqliteDatabase):
        logger.info("Skipping pre-migration backup: only supported for SQLite.")
        return

    backup_dir = os.getenv("DATABASE_BACKUP_DIRECTORY", "db_backups")
    if not backup_dir:
        logger.info("Skipping pre-migration backup: backups are disabled.")
        return

    source = db.database
    if not os.path.exists(source):
        return  # a database created by this run has nothing worth keeping

    directory = os.path.join(backup_dir, BACKUP_SUBDIR)
    os.makedirs(directory, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(directory, f"pre_migration_{timestamp}.db")

    snapshot(source, dest)
    logger.info("Backed up to %s (%d bytes)", dest, os.path.getsize(dest))
    prune(directory, int(os.getenv("DATABASE_BACKUP_RETENTION", 7)))


def _connect():
    db = create_database()
    db.connect(reuse_if_open=True)
    SchemaMigration.bind(db)
    db.create_tables([SchemaMigration])
    return db


def _applied() -> set:
    return {row.name for row in SchemaMigration.select()}


def run_migrations() -> None:
    db = _connect()
    try:
        applied = _applied()
        pending = [name for name in _discover() if name not in applied]

        if not pending:
            logger.info("No pending migrations.")
            return

        _backup(db)

        ctx = MigrationContext(db)
        for name in pending:
            module = _load(name)
            logger.info("Applying %s%s", name, _summary(module))
            with db.atomic():
                module.upgrade(ctx)
                SchemaMigration.create(name=name)

        logger.info("Applied %d migration(s).", len(pending))
    finally:
        db.close()


def show_status() -> None:
    db = _connect()
    try:
        applied = _applied()
        for name in _discover():
            logger.info("%-9s %s", "applied" if name in applied else "pending", name)
    finally:
        db.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--status", action="store_true", help="list migrations without applying them"
    )
    args = parser.parse_args()

    if args.status:
        show_status()
    else:
        run_migrations()


if __name__ == "__main__":
    main()
