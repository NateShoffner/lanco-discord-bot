import logging
import os
import uuid

import aiohttp
from discord import Message


class Attatchment:
    """Represents a downloaded attachment"""

    def __init__(self, url: str, filename: str):
        self.url = url
        self.filename = filename


class FileDownloader:
    """Download files from the internet"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def download_file(self, url: str, dir: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.read()
                    random_uuid = uuid.uuid4()

                    if not os.path.exists(dir):
                        os.makedirs(dir)

                    ext = url.split(".")[-1].split("?")[0]
                    filename = os.path.join(dir, f"{random_uuid}.{ext}")
                    with open(filename, "wb") as f:
                        f.write(data)

                    return filename

    async def download_attachments(
        self, message: Message, dir: str
    ) -> list[Attatchment]:
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

        if not os.path.exists(dir):
            os.makedirs(dir)

        for url in urls:
            filename = await self.download_file(url, dir)
            local_files.append(Attatchment(url, filename))

        return local_files
