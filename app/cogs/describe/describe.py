import base64
import os

import discord
import openai
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from utils.file_downloader import FileDownloader


class Describe(LancoCog, name="Describe", description="Describe cog"):

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.register_context_menu(
            name="Describe", callback=self.ctx_menu, errback=self.ctx_menu_error
        )
        self.client = openai.Client(api_key=os.getenv("OPENAI_API_KEY"))
        self.cache_dir = os.path.join(self.get_cog_data_directory(), "Cache")
        self.file_downloader = FileDownloader()

    async def ctx_menu(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        await interaction.response.send_message("Processing the file...")
        await interaction.channel.typing()
        description = await self.describe_attachment(message)
        await interaction.edit_original_response(content=description)

    async def ctx_menu_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        await interaction.response.send_message("An error occurred", ephemeral=True)

    def encode_image(self, image_path: str):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    async def describe_attachment(self, message: discord.Message) -> str:
        results = await self.file_downloader.download_attachments(
            message, self.cache_dir
        )

        if not results:
            return "No attachments found"

        filename = results[0].filename
        encoded = self.encode_image(filename)

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that responds in Markdown.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this image"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{encoded}"},
                        },
                    ],
                },
            ],
        )

        return response.choices[0].message.content


async def setup(bot):
    await bot.add_cog(Describe(bot))
