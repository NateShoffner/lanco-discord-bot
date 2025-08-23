import logging

import discord
from pydantic import BaseModel


class LocalEmoji(BaseModel):
    path: str
    name: str


class EmojiUploader:
    """
    Handles the setup of application emojis based off local resources.
    """

    def __init__(self, bot: discord.ext.commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    async def setup_emojis(
        self, emojis: list[LocalEmoji], force_update: bool = False
    ) -> None:
        """
        Ensure all emojis in the provided list are uploaded to the application if they do not already exist.
        """
        application_emojis = await self.bot.fetch_application_emojis()
        for emoji in emojis:
            already_exists = any(e.name == emoji.name for e in application_emojis)

            if already_exists and not force_update:
                self.logger.info(f"Emoji {emoji.name} already exists. Skipping...")
                continue

            if already_exists and force_update:
                self.logger.info(
                    f"Emoji {emoji.name} exists but force_update is True. Deleting..."
                )
                existing_emoji = next(
                    e for e in application_emojis if e.name == emoji.name
                )
                await existing_emoji.delete()

            self.logger.info(f"Emoji {emoji.name} does not exist. Uploading...")
            with open(emoji.path, "rb") as f:
                await self.bot.create_application_emoji(name=emoji.name, image=f.read())
