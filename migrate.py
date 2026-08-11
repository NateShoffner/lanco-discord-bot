"""Applies pending migrations from ``migrations/``.

Each migration runs exactly once. Applied names are recorded in the
``schema_migrations`` table, and the schema change plus that bookkeeping row
share a transaction, so a failed migration leaves nothing behind and is
retried on the next run. (SQLite makes DDL transactional; MySQL commits
implicitly on DDL, so there the rollback guarantee is best effort.)

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

from peewee import CharField, DateTimeField, Model

ROOT = os.path.dirname(os.path.abspath(__file__))

# Migrations import migrations.helpers by name, so the project root has to be
# importable no matter which directory this was invoked from.
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from migrations.helpers import MigrationContext, create_database  # noqa: E402

MIGRATIONS_DIR = os.path.join(ROOT, "migrations")
MIGRATION_PATTERN = re.compile(r"^\d{3}_\w+\.py$")

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
