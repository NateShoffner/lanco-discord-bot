import asyncio
import datetime
import logging
import os
import sqlite3

logger = logging.getLogger(__name__)


def snapshot(database_path: str, dest: str) -> None:
    """Copy a database using SQLite's online backup API.

    A plain file copy is not safe in WAL mode: recent commits live in the
    -wal sidecar, which is not copied. The previous approach checkpointed
    first, but ignored the result, and a checkpoint that reports busy leaves
    those commits only in the WAL, producing a backup that silently misses
    them. The backup API snapshots the database consistently, including
    whatever is still in the WAL, without having to block writers.

    Shared with the migration runner, which snapshots before applying anything.
    """
    source = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    try:
        target = sqlite3.connect(dest)
        try:
            with target:
                source.backup(target)
        finally:
            target.close()
    finally:
        source.close()


def prune(directory: str, keep: int) -> None:
    """Delete all but the newest ``keep`` .db files in ``directory``."""
    backups = sorted(
        [
            os.path.join(directory, f)
            for f in os.listdir(directory)
            if f.endswith(".db")
        ],
        key=os.path.getmtime,
    )
    for path in backups[: max(0, len(backups) - keep)]:
        os.remove(path)
        logger.info(f"Pruned old backup: {path}")


class DatabaseBackup:
    def __init__(self):
        self.backup_dir = os.getenv("DATABASE_BACKUP_DIRECTORY", "db_backups")
        self.backup_filename = os.getenv("DATABASE_BACKUP_FILENAME", "db_backup_{}.db")
        self.backup_interval = int(os.getenv("DATABASE_BACKUP_INTERVAL", 86400))
        self.backup_retention = int(os.getenv("DATABASE_BACKUP_RETENTION", 7))
        self.database_path = os.getenv("SQLITE_DB")
        self._task = None

    def start(self):
        if not self.backup_dir or not self.database_path:
            logger.info(
                "Database backup disabled — no backup directory or database path configured."
            )
            return

        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)

        logger.info(
            f"Starting database backup task every {self.backup_interval} seconds"
        )
        self._task = asyncio.create_task(self._loop())

    def stop(self):
        if self._task:
            self._task.cancel()
            self._task = None

    async def _loop(self):
        await self.backup()
        while True:
            await asyncio.sleep(self.backup_interval)
            await self.backup()

    async def backup(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(self.backup_dir, self.backup_filename.format(timestamp))

        logger.info(f"Backing up database to {dest}")
        try:
            await asyncio.to_thread(self._snapshot, dest)
            size = os.path.getsize(dest)
            logger.info(f"Database backed up to {dest} ({size} bytes)")
            await asyncio.to_thread(self._prune_old_backups)
        except Exception:
            logger.exception("Database backup failed")

    def _snapshot(self, dest: str) -> None:
        snapshot(self.database_path, dest)

    def _prune_old_backups(self):
        prune(self.backup_dir, self.backup_retention)
