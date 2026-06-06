import asyncio
import datetime
import logging
import os
import shutil

logger = logging.getLogger(__name__)


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
            await asyncio.to_thread(shutil.copy2, self.database_path, dest)
            logger.info(f"Database backed up to {dest}")
            await asyncio.to_thread(self._prune_old_backups)
        except Exception as e:
            logger.error(f"Database backup failed: {e}")

    def _prune_old_backups(self):
        backups = sorted(
            [
                os.path.join(self.backup_dir, f)
                for f in os.listdir(self.backup_dir)
                if f.endswith(".db")
            ],
            key=os.path.getmtime,
        )
        to_delete = backups[: max(0, len(backups) - self.backup_retention)]
        for path in to_delete:
            os.remove(path)
            logger.info(f"Pruned old backup: {path}")
