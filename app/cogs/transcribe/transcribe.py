import os

import discord
import whisper
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from pydub import AudioSegment
from utils.command_utils import is_bot_owner_or_admin
from utils.voice_message import download_voice_message, is_voice_message

from .models import TranscribeConfig


class Transcribe(LancoCog, name="Transcribe", description="Transcribe cog"):

    g = app_commands.Group(name="transcribe", description="Transcribe commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.cache_dir = os.path.join(self.get_cog_data_directory(), "Cache")
        self.bot.database.create_tables([TranscribeConfig])
        self.model = whisper.load_model("base", device="cpu")
        self.register_context_menu(
            name="Transcribe", callback=self.ctx_menu, errback=self.ctx_menu_error
        )

    async def ctx_menu(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        if not is_voice_message(message):
            await interaction.response.send_message(
                "This is not a voice message", ephemeral=True
            )
            return

        await interaction.response.send_message("✨ Transcribing...", ephemeral=True)

        transcription = await self.transcribe(message)
        await interaction.edit_original_response(
            content=f"✨ Transcription: {transcription}"
        )

    async def ctx_menu_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        pass

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
    async def on_message(self, message: discord.Message):
        if not is_voice_message(message):
            return

        transcription = await self.transcribe(message)
        if transcription:
            await message.reply(f"✨ Transcription: {transcription}")

    async def transcribe(self, message: discord.Message):
        config = TranscribeConfig.get_or_none(guild_id=message.guild.id)
        if not config or not config.enabled:
            return

        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

        ogg_file_path = await download_voice_message(message, self.cache_dir)
        ogg_audio = AudioSegment.from_file(ogg_file_path, format="ogg")

        wav_file_path = os.path.join(self.cache_dir, f"{message.id}.wav")
        ogg_audio.export(wav_file_path, format="wav")

        try:
            result = self.model.transcribe(wav_file_path)
            transcription = result["text"]
        except Exception as e:
            self.logger.error(e)

        # cleanup
        os.remove(ogg_file_path)
        os.remove(wav_file_path)

        return transcription


async def setup(bot):
    await bot.add_cog(Transcribe(bot))
