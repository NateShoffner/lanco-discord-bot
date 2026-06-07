import inspect
import logging
import re
from pathlib import Path

from discord import app_commands
from discord.ext import commands
from pydantic import BaseModel


class LancoCog(commands.Cog, name="LancoCog", description="Base class for all cogs"):
    @property
    def bot(self) -> commands.Bot:
        return self._bot

    def __init__(self, bot: commands.Bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bot = bot
        self.logger = logging.getLogger(self.get_cog_name())
        self.context_menus = []
        self._tracked_tasks = []

    def track_task(self, task):
        """Register a background task to be cancelled on cog unload."""
        self._tracked_tasks.append(task)
        return task

    async def cog_load(self):
        self.logger.info(f"{self.get_cog_name()} cog loaded")

    def get_cog_name(self):
        return self.qualified_name

    def get_cog_data_directory(self):
        return f"data/{self.get_cog_name()}"

    def get_cog_file_path(self, relative: bool = False) -> Path:
        path = Path(inspect.getfile(self.__class__))
        if relative:
            path = path.relative_to(Path.cwd() / "app")
        return path

    def get_cog_directory(self, relative: bool = False) -> Path:
        return self.get_cog_file_path(relative).parent

    def register_context_menu(self, name: str, callback, errback=None, **kwargs):
        ctx_menu = app_commands.ContextMenu(name=name, callback=callback, **kwargs)
        if errback:
            ctx_menu.error(errback)
        self.bot.tree.add_command(ctx_menu)
        self.context_menus.append(ctx_menu)

    async def cog_unload(self):
        self.logger.info(f"{self.get_cog_name()} cog unloaded")

        for task in self._tracked_tasks:
            task.cancel()
        self._tracked_tasks.clear()

        for ctx_menu in self.context_menus:
            self.bot.tree.remove_command(ctx_menu.name, type=ctx_menu.type)

        self.bot.url_handlers = [h for h in self.bot.url_handlers if h.cog is not self]


class UrlHandler(BaseModel):
    url_pattern: re.Pattern
    cog: LancoCog
    example_url: str

    class Config:
        arbitrary_types_allowed = True
