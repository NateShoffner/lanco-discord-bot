"""Shared plumbing for migration scripts.

Every migration exposes a single ``upgrade(ctx)`` function and does its work
through the :class:`MigrationContext` it is handed. The context owns the
connection, the dialect-appropriate migrator, and a set of idempotent
operations, so no migration opens its own database or hand-rolls a
"does this column already exist" check.

Operations are idempotent on purpose. The ``schema_migrations`` tracking table
was introduced after several migrations had already been applied in
production, so a migration must be a no-op when the database already has the
change. Operations against a missing table are skipped rather than raising:
cogs create their own tables at load time, so a table may legitimately not
exist yet on a fresh database or when a cog is blacklisted.

Migrations never import models from ``app``. A migration is a snapshot of the
schema at one point in time; importing a live model would silently change what
an old migration does every time that model evolves.
"""

import logging
import os

from dotenv import load_dotenv
from peewee import Database, Entity, Index, Model, MySQLDatabase, SqliteDatabase
from playhouse.migrate import MySQLMigrator, SchemaMigrator, SqliteMigrator, migrate

logger = logging.getLogger("migrate")


def create_database() -> Database:
    """Build the database described by the environment.

    Mirrors ``init_db()`` in ``app/main.py`` but without importing the bot, so
    migrations can run in a container step of their own. SQLite pragmas are
    left at their defaults here: the migrator rebuilds tables to alter columns,
    which does not mix well with foreign key enforcement.
    """
    load_dotenv()
    db_type = os.getenv("DB_TYPE", "sqlite").lower()

    if db_type == "sqlite":
        path = os.getenv("SQLITE_DB", "data/lancobot.db")
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        return SqliteDatabase(path)

    if db_type == "mysql":
        return MySQLDatabase(
            os.getenv("MYSQL_DB"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            host=os.getenv("MYSQL_HOST"),
            port=int(os.getenv("MYSQL_PORT", 3306)),
        )

    raise ValueError(f"Unsupported database type: {db_type}")


def create_migrator(db: Database) -> SchemaMigrator:
    return MySQLMigrator(db) if isinstance(db, MySQLDatabase) else SqliteMigrator(db)


class MigrationContext:
    """Idempotent schema operations bound to a single connection."""

    def __init__(self, db: Database):
        self.db = db
        self.migrator = create_migrator(db)

    # introspection

    def table_exists(self, table: str) -> bool:
        return table in self.db.get_tables()

    def column_exists(self, table: str, column: str) -> bool:
        return column in self._column_names(table)

    def index_exists(self, table: str, index: str) -> bool:
        return index in {idx.name for idx in self.db.get_indexes(table)}

    # operations

    def add_columns(self, table: str, **columns) -> None:
        """Add each ``name=Field(...)`` column that is not already present."""
        if not self._require_table(table):
            return

        existing = self._column_names(table)
        for name, field in columns.items():
            if name in existing:
                logger.info("  %s.%s already exists, skipping", table, name)
                continue
            migrate(self.migrator.add_column(table, name, field))
            logger.info("  added %s.%s", table, name)

    def drop_not_null(self, table: str, *columns: str) -> None:
        """Make each column nullable if it is currently NOT NULL."""
        if not self._require_table(table):
            return

        by_name = {col.name: col for col in self.db.get_columns(table)}
        for name in columns:
            column = by_name.get(name)
            if column is None:
                logger.info("  %s.%s does not exist, skipping", table, name)
            elif column.null:
                logger.info("  %s.%s is already nullable, skipping", table, name)
            else:
                migrate(self.migrator.drop_not_null(table, name))
                logger.info("  dropped NOT NULL from %s.%s", table, name)

    def rename_table(self, old: str, new: str) -> None:
        tables = set(self.db.get_tables())
        if old not in tables:
            logger.info("  table %s does not exist, skipping", old)
            return
        if new in tables:
            logger.info("  table %s already exists, skipping", new)
            return

        migrate(self.migrator.rename_table(old, new))
        logger.info("  renamed %s to %s", old, new)

    def create_table(self, model: type[Model]) -> None:
        """Create the table for a model declared inside a migration.

        Only the table is created; declare indexes explicitly with
        :meth:`create_index` so their names stay stable across databases.
        """
        table = model._meta.table_name
        if self.table_exists(table):
            logger.info("  table %s already exists, skipping", table)
            return

        model.bind(self.db)
        self.db.create_tables([model])
        logger.info("  created table %s", table)

    def create_index(
        self, table: str, name: str, columns: list[str], unique: bool = False
    ) -> None:
        if not self._require_table(table):
            return
        if self.index_exists(table, name):
            logger.info("  index %s already exists, skipping", name)
            return

        # safe=False: IF NOT EXISTS is not valid index syntax on MySQL, and the
        # check above already makes this a no-op when the index is present.
        index = Index(
            name,
            table,
            [Entity(column) for column in columns],
            unique=unique,
            safe=False,
        )
        self.db.execute(index)
        logger.info("  created index %s on %s", name, table)

    def execute(self, sql: str, *params) -> None:
        """Escape hatch for changes the helpers above do not cover."""
        self.db.execute_sql(sql, params)

    # internals

    def _column_names(self, table: str) -> set:
        return {col.name for col in self.db.get_columns(table)}

    def _require_table(self, table: str) -> bool:
        if self.table_exists(table):
            return True
        logger.info("  table %s does not exist, skipping", table)
        return False
