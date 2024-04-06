from dataclasses import dataclass
from enum import Enum
import inspect
import os
import uuid
import aiohttp
from discord import Message
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


class Attatchment:
    def __init__(self, url: str, filename: str):
        self.url = url
        self.filename = filename


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

    async def download_attachments(self, message: Message) -> list[Attatchment]:
        """Download attachments from a message"""
        local_files = []
        urls = []
        if message.attachments:
            self.logger.info("Attachments found in message")
            for a in message.attachments:
                url = a.url
                urls.append(url)
        elif message.embeds:
            self.logger.info("Embed found in message")
            for embed in message.embeds:
                if embed.image:
                    url = embed.image.proxy_url
                if embed.video:
                    proxy_url = embed.video.proxy_url

                    self.logger.info(f"Proxy URL: {proxy_url}")

                    if "tenor.com" in proxy_url:
                        # tenor seems to ignore the extension but instead uses the URL path to determine the file type

                        # gif
                        # https://media.tenor.com/jv1uzXK_ELwAAAAC/fullmetal-alchemist.gif
                        # mp4
                        # https://media.tenor.com/jv1uzXK_ELwAAAPo/fullmetal-alchemist.gif

                        # mp4
                        # https://media.tenor.com/M0DJo6-jF7AAAAPo/anime-responsibilities.mp4
                        # gif
                        # https://media.tenor.com/M0DJo6-jF7AAAAAC/anime-responsibilities.gif

                        # hacky way to get the original url and get the original GIF
                        # Ex: https://images-ext-2.discordapp.net/external/PHVkBmSMxJdxhSl2dlVt9_VL4tiHyn0blDb9ZBNWLjQ/https/media.tenor.com/M0DJo6-jF7AAAAPo/anime-responsibilities.mp4

                        # parse the proxy url and replace the extension, subdomain, and path
                        tenor_url = proxy_url.split("/https/")[1]
                        url_split = tenor_url.split("/")
                        path = url_split[1]
                        if path.endswith("Po"):
                            path = path[:-2] + "AC"
                        new_url = f"https://c.tenor.com/{path}/tenor.gif"
                        url = new_url
                        urls.append(url)

                        # https://media.tenor.com/jv1uzXK_ELwAAAPo/fullmetal-alchemist.mp4
                        # https://c.tenor.com/jv1uzXK_ELwAAAAC/tenor.gif
                        # https://c.tenor.com/jv1uzXK_ELwAAAC/fullmetal-alchemist.gif
            self.logger.info(f"URL: {url}")

        for url in urls:
            # download the image
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.read()
                        random_uuid = uuid.uuid4()

                        if not os.path.exists(self.cache_dir):
                            os.makedirs(self.cache_dir)

                        ext = url.split(".")[-1].split("?")[0]
                        filename = os.path.join(self.cache_dir, f"{random_uuid}.{ext}")
                        with open(filename, "wb") as f:
                            f.write(data)

                        local_files.append(Attatchment(url, filename))

        return local_files
