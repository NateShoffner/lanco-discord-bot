"""
DatabaseBackupper Cog

Description:
Routinely backs up the database to a specified directory with a timestamped filename.
"""

import datetime
import os
import shutil

from cogs.lancocog import LancoCog
from discord.ext import commands, tasks
from utils.command_utils import is_bot_owner


class DatabaseBackupper(
    LancoCog,
    name="Database Backupper",
    description="Routinely backs up the database to a specified directory with a timestamped filename.",
):
    def __init__(self, bot):
        super().__init__(bot)

        self.backup_dir = os.getenv("DATABASE_BACKUP_DIRECTORY", "db_backups")
        self.backup_filename = os.getenv("DATABASE_BACKUP_FILENAME", "db_backup_{}.sqlite")
        self.backup_interval = int(
            os.getenv("DATABASE_BACKUP_INTERVAL", 8640)
        )  # default to 24 hours

        self.database_path = os.getenv("SQLITE_DB")

        if not self.backup_dir or not self.backup_dir.strip():
            print("Database backup is disabled. No backup directory specified.")
            return

        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info(
            f"Starting database backup task every {self.backup_interval} seconds"
        )
        self.backup_db_task.change_interval(seconds=self.backup_interval)
        self.backup_db_task.start()

        # perform an initial backup immediately
        await self.backup_db()

    @tasks.loop()
    async def backup_db_task(self):
        await self.backup_db()

    async def backup_db(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = os.path.join(
            self.backup_dir, self.backup_filename.format(timestamp)
        )

        self.logger.info(
            f"Backing up database from {self.database_path} to {backup_filename}"
        )

        try:
            shutil.copy2(self.database_path, backup_filename)
            print(f"Database backed up to {backup_filename}")
        except Exception as e:
            print(f"Failed to back up database: {e}")

    @commands.command(name="backup_db", description="Manually back up the database")
    @is_bot_owner()
    async def backup_db_command(self, ctx: commands.Context):
        await self.backup_db()
        await ctx.send("Database backup triggered.")


async def setup(bot):
    await bot.add_cog(DatabaseBackupper(bot))
