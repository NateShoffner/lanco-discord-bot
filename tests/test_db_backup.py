"""Tests for DatabaseBackup.

The behaviour that matters here is WAL-awareness. In WAL mode, commits live in
the -wal sidecar until a checkpoint moves them into the main database file, so
copying the file alone can produce a backup that is missing recent commits, or
that has no usable content at all. These tests pin the snapshot to the logical
database rather than the file on disk.
"""

import os
import sqlite3

import pytest
from utils.db_backup import DatabaseBackup


@pytest.fixture
def wal_db(tmp_path):
    """A WAL database with commits deliberately left uncheckpointed."""
    path = str(tmp_path / "live.db")

    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=wal")
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
    conn.commit()
    conn.executemany(
        "INSERT INTO t (val) VALUES (?)", [(f"row{i}",) for i in range(500)]
    )
    conn.commit()

    # A second connection holding a read transaction prevents checkpointing,
    # which is the state a busy checkpoint leaves behind in production.
    blocker = sqlite3.connect(path)
    blocker.execute("BEGIN")
    blocker.execute("SELECT COUNT(*) FROM t").fetchone()

    conn.executemany(
        "INSERT INTO t (val) VALUES (?)", [(f"late{i}",) for i in range(200)]
    )
    conn.commit()

    yield path, conn

    blocker.close()
    conn.close()


def _backup_for(path, tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB", path)
    monkeypatch.setenv("DATABASE_BACKUP_DIRECTORY", str(tmp_path / "backups"))
    return DatabaseBackup()


def test_checkpoint_is_blocked_in_this_scenario(wal_db):
    """Guard the premise: without this, the other tests prove nothing."""
    path, conn = wal_db
    busy, _log, _checkpointed = conn.execute(
        "PRAGMA wal_checkpoint(TRUNCATE)"
    ).fetchone()
    assert busy == 1, "expected a blocked checkpoint for these tests to be meaningful"


def test_snapshot_captures_wal_resident_commits(wal_db, tmp_path, monkeypatch):
    path, conn = wal_db
    expected = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]

    dest = str(tmp_path / "backup.db")
    _backup_for(path, tmp_path, monkeypatch)._snapshot(dest)

    restored = sqlite3.connect(dest)
    try:
        assert restored.execute("SELECT COUNT(*) FROM t").fetchone()[0] == expected
    finally:
        restored.close()


def test_snapshot_beats_a_plain_file_copy(wal_db, tmp_path, monkeypatch):
    """A file copy of the same database is incomplete or unusable."""
    import shutil

    path, conn = wal_db
    expected = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]

    copied = str(tmp_path / "copied.db")
    shutil.copy2(path, copied)
    try:
        copy_rows = (
            sqlite3.connect(copied).execute("SELECT COUNT(*) FROM t").fetchone()[0]
        )
    except sqlite3.DatabaseError:
        copy_rows = None  # the copy has no usable table at all

    assert copy_rows != expected, (
        "a plain file copy unexpectedly captured everything, so this scenario no "
        "longer reproduces the failure the backup API exists to avoid"
    )


def test_snapshot_preserves_content_not_just_row_count(wal_db, tmp_path, monkeypatch):
    path, conn = wal_db
    dest = str(tmp_path / "backup.db")
    _backup_for(path, tmp_path, monkeypatch)._snapshot(dest)

    restored = sqlite3.connect(dest)
    try:
        assert restored.execute(
            "SELECT val FROM t WHERE val = 'late199'"
        ).fetchone() == ("late199",)
        assert restored.execute("SELECT val FROM t WHERE val = 'row0'").fetchone() == (
            "row0",
        )
    finally:
        restored.close()


@pytest.mark.asyncio
async def test_backup_writes_a_file_and_prunes(wal_db, tmp_path, monkeypatch):
    path, _conn = wal_db
    monkeypatch.setenv("DATABASE_BACKUP_RETENTION", "2")
    backup = _backup_for(path, tmp_path, monkeypatch)
    os.makedirs(backup.backup_dir, exist_ok=True)

    # distinct filenames, since the real name is timestamped to the second
    for i in range(4):
        backup.backup_filename = f"db_backup_{i}_{{}}.db"
        await backup.backup()

    remaining = [f for f in os.listdir(backup.backup_dir) if f.endswith(".db")]
    assert len(remaining) == 2, remaining


@pytest.mark.asyncio
async def test_backup_failure_does_not_raise(tmp_path, monkeypatch):
    """A failing backup is logged, never propagated into the bot's task loop."""
    monkeypatch.setenv("SQLITE_DB", str(tmp_path / "does_not_exist.db"))
    monkeypatch.setenv("DATABASE_BACKUP_DIRECTORY", str(tmp_path / "backups"))
    backup = DatabaseBackup()
    os.makedirs(backup.backup_dir, exist_ok=True)

    monkeypatch.setattr(
        backup, "_snapshot", lambda dest: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    await backup.backup()  # must not raise
