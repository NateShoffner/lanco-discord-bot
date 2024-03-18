from dataclasses import dataclass
import inspect
import os
from discord.ext import commands
import logging


@dataclass
class CogDefinition:
    """Represents file-system information about a cog"""

    path: str
    """ The path to the cog directory  """
    name: str
    """ The file-system name of the cog"""
    qualified_name: str
    """ The fully qualified name of the cog (dot-separated path) """
    entry_point: str
    """ The entry point script for the cog"""


def get_cog_def(name: str, cogs_dir: str) -> CogDefinition:
    """Get the cog definition for a cog based on the cog name and the cogs directory"""
    path = os.path.normpath(os.path.join(cogs_dir, name))
    cogs_dir_name = os.path.basename(cogs_dir)
    qualified_name = f"{cogs_dir_name}.{name}.{name}"
    entry_point = os.path.normpath(f"{path}/{name}.py")
    return CogDefinition(path, name, qualified_name, entry_point)


class LancoCog(commands.Cog, name="LancoCog", description="Base class for all cogs"):
    def __init__(self, bot: commands.Bot, *args, **kwargs):
        self.bot = bot
        self.logger = logging.getLogger(self.get_cog_name())
        self.cog_def = None

    def set_cog_def(self, cog_def: CogDefinition):
        """Set the cog definition"""
        self.cog_def = cog_def

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info(f"{self.get_cog_name()} cog loaded")

    def get_cog_name(self):
        """Get the name of the cog"""
        return self.qualified_name

    def get_class_name(self):
        """Get the class name of the cog"""
        return self.__class__.__name__

    def get_cog_data_directory(self):
        """Get the data directory for the cog"""
        return f"data/{self.get_cog_name()}"

    def get_cog_file_path(self, relative: bool = False):
        """Get the file path for the cog"""
        path = inspect.getfile(self.__class__)
        if relative:
            path = os.path.relpath(path)
            # remove top-level directory
            path = os.path.join(*path.split(os.sep)[1:])
        return path

    def get_dotted_path(self):
        """Get the dotted path for the cog"""
        dotted = self.get_cog_file_path(True).replace(os.sep, ".")
        dotted = dotted.replace(".py", "")
        return dotted
