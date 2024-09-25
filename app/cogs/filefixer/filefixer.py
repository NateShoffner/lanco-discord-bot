import os

import discord
import imageio
import pillow_heif
from cogs.lancocog import LancoCog
from discord.ext import commands
from PIL import Image


class FileFixer(LancoCog, name="FileFixer", description="Attempt to fix files"):

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.cache_dir = os.path.join(self.get_cog_data_directory(), "Cache")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if message.attachments:
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
                    downloaded = await self.download_attachments(
                        message, self.cache_dir
                    )
                    fixer = fixers[extension]
                    fix_result = await fixer(downloaded[0].filename)

                    if fix_result:
                        await self.send_fixed_embed(message, fix_result)

    async def send_fixed_embed(
        self, original_message: discord.Message, fixed_file: str
    ):
        author = original_message.author
        filename = os.path.basename(fixed_file)

        file = discord.File(fixed_file, filename=filename)
        embed = discord.Embed(title="Fixed ||User Error|| Unsupported File Type")
        embed.description = f"Original file by {author.display_name}"
        embed.set_image(url=f"attachment://{filename}")
        await original_message.channel.send(file=file, embed=embed)

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
