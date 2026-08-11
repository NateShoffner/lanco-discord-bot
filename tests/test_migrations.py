"""Migration runner tests.

Migrations must be safe to run against a database at any point in its history:
a brand new file, a database that predates the tracking table, and one that is
already fully migrated.
"""

import sqlite3

import pytest
from peewee import CharField

import migrate

# Roughly the schema as it stood before 001, enough to exercise the renames,
# the added columns and the guild_configs dedupe.
LEGACY_SCHEMA = """
CREATE TABLE instafix_config (id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL);
CREATE TABLE twitterfix_config (id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL);
CREATE TABLE tiktokfix_config (id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL);
CREATE TABLE "auto-response" (id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL);
CREATE TABLE incidents_config (id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL);
CREATE TABLE custom_commands (
    id INTEGER PRIMARY KEY,
    guild_id INTEGER NOT NULL,
    command_name VARCHAR(255) NOT NULL,
    command_response VARCHAR(255) NOT NULL
);
CREATE TABLE guild_configs (id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL);

INSERT INTO custom_commands (guild_id, command_name, command_response)
    VALUES (1, 'foo', 'bar');
INSERT INTO guild_configs (guild_id) VALUES (1), (1), (2);
"""


def schema_of(path) -> list:
    conn = sqlite3.connect(path)
    try:
        return conn.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
    finally:
        conn.close()


def columns(path, table) -> dict:
    conn = sqlite3.connect(path)
    try:
        return {row[1]: row for row in conn.execute(f'PRAGMA table_info("{table}")')}
    finally:
        conn.close()


@pytest.fixture
def legacy_db(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript(LEGACY_SCHEMA)
    conn.commit()
    conn.close()

    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_DB", str(path))
    return path


def test_runs_against_an_empty_database(tmp_path, monkeypatch):
    path = tmp_path / "fresh.db"
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_DB", str(path))

    migrate.run_migrations()

    applied = {row[0] for row in schema_of(path) if row[0] == "table"}
    assert applied  # tracking table exists, nothing raised


def test_applies_legacy_schema_changes(legacy_db):
    migrate.run_migrations()

    tables = {row[1] for row in schema_of(legacy_db) if row[0] == "table"}
    assert "instaembed_config" in tables
    assert "instafix_config" not in tables
    assert "auto_response" in tables

    custom_commands = columns(legacy_db, "custom_commands")
    assert "cooldown" in custom_commands
    assert custom_commands["cooldown"][3] == 0  # nullable, see 009
    assert custom_commands["command_response"][3] == 0  # nullable, see 008


def test_dedupes_guild_configs(legacy_db):
    migrate.run_migrations()

    conn = sqlite3.connect(legacy_db)
    try:
        guild_ids = [
            row[0] for row in conn.execute("SELECT guild_id FROM guild_configs")
        ]
    finally:
        conn.close()

    assert sorted(guild_ids) == [1, 2]


def test_every_migration_is_recorded(legacy_db):
    migrate.run_migrations()

    conn = sqlite3.connect(legacy_db)
    try:
        recorded = {
            row[0] for row in conn.execute("SELECT name FROM schema_migrations")
        }
    finally:
        conn.close()

    assert recorded == set(migrate._discover())


def test_rerunning_from_scratch_is_a_no_op(legacy_db):
    """A database migrated before the tracking table existed must survive a
    full replay, which is why every operation checks the current schema."""
    migrate.run_migrations()
    before = schema_of(legacy_db)

    conn = sqlite3.connect(legacy_db)
    conn.execute("DELETE FROM schema_migrations")
    conn.commit()
    conn.close()

    migrate.run_migrations()
    assert schema_of(legacy_db) == before


def test_backs_up_before_applying(legacy_db, tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_BACKUP_DIRECTORY", str(tmp_path / "backups"))

    migrate.run_migrations()

    backups = list((tmp_path / "backups" / migrate.BACKUP_SUBDIR).glob("*.db"))
    assert len(backups) == 1

    # the snapshot predates the migrations, so it still has the old table names
    restored = {row[1] for row in schema_of(backups[0]) if row[0] == "table"}
    assert "instafix_config" in restored
    assert "instaembed_config" not in restored


def test_backup_is_skipped_when_nothing_is_pending(legacy_db, tmp_path, monkeypatch):
    """Every container start runs the migrator; only real work earns a backup."""
    monkeypatch.setenv("DATABASE_BACKUP_DIRECTORY", str(tmp_path / "backups"))
    migrate.run_migrations()

    migrate.run_migrations()

    backups = list((tmp_path / "backups" / migrate.BACKUP_SUBDIR).glob("*.db"))
    assert len(backups) == 1


def test_backup_failure_aborts_the_run(legacy_db, tmp_path, monkeypatch):
    """No restore point means no migration."""
    monkeypatch.setenv("DATABASE_BACKUP_DIRECTORY", str(tmp_path / "backups"))

    def explode(source, dest):
        raise OSError("no space left on device")

    monkeypatch.setattr(migrate, "snapshot", explode)

    with pytest.raises(OSError):
        migrate.run_migrations()

    tables = {row[1] for row in schema_of(legacy_db) if row[0] == "table"}
    assert "instafix_config" in tables  # 001 never ran
    assert "instaembed_config" not in tables

    conn = sqlite3.connect(legacy_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 0
    finally:
        conn.close()


def test_failed_migration_leaves_no_trace(legacy_db, monkeypatch):
    migrate.run_migrations()
    before = schema_of(legacy_db)

    def explode(ctx):
        ctx.add_columns("guild_configs", probe=CharField(null=True))
        raise RuntimeError("boom")

    module = type("module", (), {"upgrade": staticmethod(explode), "__doc__": None})
    monkeypatch.setattr(migrate, "_discover", lambda: ["999_probe.py"])
    monkeypatch.setattr(migrate, "_load", lambda name: module)

    with pytest.raises(RuntimeError):
        migrate.run_migrations()

    assert schema_of(legacy_db) == before
