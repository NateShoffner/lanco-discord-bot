import io
import os

import discord
import whisper
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from pydub import AudioSegment
from utils.command_utils import is_bot_owner_or_admin

from .models import TranscribeConfig


class Transcribe(LancoCog, name="Transcribe", description="Transcribe cog"):

    g = app_commands.Group(name="transcribe", description="Transcribe commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.cache_dir = os.path.join(self.get_cog_data_directory(), "Cache")
        self.bot.database.create_tables([TranscribeConfig])
        self.model = whisper.load_model("base", device="cpu")

    @g.command(
        name="toggle", description="Toggle transcription services for this server"
    )
    @is_bot_owner_or_admin()
    async def toggle(self, interaction: discord.Interaction):
        config, created = TranscribeConfig.get_or_create(guild_id=interaction.guild.id)
        if created:
            config.enabled = True
            config.save()
            await interaction.response.send_message("Transcription services enabled")
        else:
            config.delete_instance()
            await interaction.response.send_message("Transcription services disabled")

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        if len(message.attachments) != 1:
            return

        if message.attachments[0].content_type != "audio/ogg":
            return

        config = TranscribeConfig.get_or_none(guild_id=message.guild.id)
        if not config or not config.enabled:
            return

        msg = await message.reply("✨ Transcribing...", mention_author=False)

        voice_file = await message.attachments[0].read()
        voice_file = io.BytesIO(voice_file)

        ogg_file_path = os.path.join(self.cache_dir, f"{message.id}.ogg")
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        with open(ogg_file_path, "wb") as f:
            f.write(voice_file.getvalue())

        ogg_audio = AudioSegment.from_file(ogg_file_path, format="ogg")

        wav_filename = os.path.join(self.cache_dir, f"{message.id}.wav")
        ogg_audio.export(wav_filename, format="wav")

        try:
            result = self.model.transcribe(wav_filename)
            transcription = result["text"]
            await msg.edit(content=f"✨ Transcription: {transcription}")
        except Exception as e:
            await msg.edit(content=f"✨ Transcription failed!")
            self.logger.error(e)

        # cleanup
        os.remove(ogg_file_path)
        os.remove(wav_filename)


async def setup(bot):
    await bot.add_cog(Transcribe(bot))
