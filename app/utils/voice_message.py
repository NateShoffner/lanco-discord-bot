import io
import os

import discord


def is_voice_message(message: discord.Message) -> bool:
    """Check if a message is a voice message"""

    if len(message.attachments) != 1:
        return False

    if message.attachments[0].content_type != "audio/ogg":
        return False

    return True


async def download_voice_message(message: discord.Message, filename: str) -> str:
    """Download a voice message attachment"""

    if not is_voice_message(message):
        raise ValueError("The message is not a voice message")

    voice_file = await message.attachments[0].read()
    voice_file = io.BytesIO(voice_file)

    ogg_file_path = os.path.join(filename, f"{message.id}.ogg")
    with open(ogg_file_path, "wb") as f:
        f.write(voice_file.getvalue())

    return ogg_file_path
