import os

import discord
import imageio
import pillow_heif
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from PIL import Image
from utils.command_utils import is_bot_owner_or_admin
from utils.file_downloader import FileDownloader

from .models import FileFixerConfig


class FileFixer(LancoCog, name="FileFixer", description="Attempt to fix files"):

    g = app_commands.Group(name="filefixer", description="FileFixer commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.cache_dir = os.path.join(self.get_cog_data_directory(), "Cache")
        self.bot.database.create_tables([FileFixerConfig])
        self.file_downloader = FileDownloader()

    @g.command(
        name="toggle", description="Toggle support for fixing unsupported file types"
    )
    @is_bot_owner_or_admin()
    async def toggle(self, interaction: discord.Interaction):
        config, created = FileFixerConfig.get_or_create(guild_id=interaction.guild.id)
        if created:
            config.enabled = True
            config.save()
            await interaction.response.send_message("FileFixer enabled for this server")
        else:
            config.delete_instance()
            await interaction.response.send_message(
                "FileFixer disabled for this server"
            )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if message.attachments:

            config = FileFixerConfig.get_or_none(guild_id=message.guild.id)
            if not config or not config.enabled:
                return

            for att in message.attachments:
                # TODO - handle multiple attachments
                if len(message.attachments) > 1:
                    self.logger.info("More than one attachment found")
                    return

                fixers = {
                    "avif": self.fix_avif,
                    "heic": self.fix_heic,
                }

                extension = att.filename.lower().split(".")[-1]

                if extension in fixers:
                    downloaded = await self.file_downloader.download_attachments(
                        message, self.cache_dir
                    )
                    fixer = fixers[extension]
                    fix_result = await fixer(downloaded[0].filename)

                    if fix_result:
                        await self.send_fixed_embed(
                            message, fix_result, f".{extension}"
                        )

    async def send_fixed_embed(
        self,
        original_message: discord.Message,
        fixed_file: str,
        original_file_type: str,
    ):
        author = original_message.author
        filename = os.path.basename(fixed_file)

        file = discord.File(fixed_file, filename=filename)
        embed = discord.Embed(
            title=f"Converted Unsupported File Type ({original_file_type})"
        )
        embed.set_image(url=f"attachment://{filename}")
        await original_message.reply(file=file, embed=embed)

    async def fix_avif(self, local_path: str) -> str:
        try:
            avif_image = imageio.imread(local_path)
            output_file = local_path.lower().replace(".avif", ".png")

            imageio.imwrite(output_file, avif_image, format="PNG")
            self.logger.info(f"Conversion successful: {local_path} -> {output_file}")
            return output_file
        except Exception as e:
            self.logger.error(f"Error: {e}")

    async def fix_heic(self, local_path: str) -> str:
        pillow_heif.register_heif_opener()

        try:
            heic_image = Image.open(local_path)
            output_file = local_path.lower().replace(".heic", ".png")

            heic_image.save(output_file, "PNG")
            self.logger.info(f"Conversion successful: {local_path} -> {output_file}")
            return output_file
        except Exception as e:
            self.logger.error(f"Error: {e}")


async def setup(bot):
    await bot.add_cog(FileFixer(bot))
