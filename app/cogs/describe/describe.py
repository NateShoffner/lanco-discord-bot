import mimetypes
import os

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from pydantic import BaseModel, Field
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.exceptions import ModelHTTPError
from utils.file_downloader import FileDownloader
from utils.tracked_message import track_message_ids


class FileDetails(BaseModel):
    description: str = Field(
        ...,
        description="A detailed description of the image, including any relevant context or information.",
    )


# One paid vision call per invocation, so it is rate limited per user.
VISION_COOLDOWN = 30.0


class Describe(
    LancoCog,
    name="Describe",
    description="Provides context menu for providing descriptions of images",
):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.register_context_menu(
            name="Describe", callback=self.ctx_menu, errback=self.ctx_menu_error
        )
        self.agent = Agent(
            model="openai:gpt-5-nano",
            system_prompt="Describe this image.",
            output_type=FileDetails,
        )
        self.cache_dir = os.path.join(self.get_cog_data_directory(), "Cache")
        self.file_downloader = FileDownloader()

    @app_commands.checks.cooldown(1, VISION_COOLDOWN)
    async def ctx_menu(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        await self.send_description(interaction, message)

    async def ctx_menu_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        # nothing was sent yet, so edit_original_response below would fail
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"On cooldown, try again in {error.retry_after:.0f}s.", ephemeral=True
            )
            return
        self.logger.error(error)
        await interaction.edit_original_response(
            content="An error occurred while processing the request."
        )

    @track_message_ids()
    async def send_description(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> discord.Message:
        await interaction.response.send_message("Processing the file...")
        await interaction.channel.typing()
        details = await self.get_attachment_details(message)
        msg = await interaction.edit_original_response(content=details.description)
        return msg

    async def get_attachment_details(self, message: discord.Message) -> FileDetails:
        results = await self.file_downloader.download_attachments(
            message, self.cache_dir
        )

        if not results:
            return "No attachments found"

        filename = results[0].filename

        with open(filename, "rb") as f:
            image_bytes = f.read()

        # TODO might want to use python-magic so it's content-based
        mime_type, _ = mimetypes.guess_type(filename)

        try:
            result = await self.agent.run(
                [
                    "Describe this image and provide any insight that might be useful.",
                    BinaryContent(data=image_bytes, media_type=mime_type),
                ]
            )
        except ModelHTTPError as e:
            self.logger.error("ModelHTTPError during agent run: %s", e)
            raise
        except Exception as e:
            self.logger.error("Unexpected error during agent run: %s", e)
            raise

        # cleanup
        for r in results:
            os.remove(r.filename)

        return result.output


async def setup(bot):
    await bot.add_cog(Describe(bot))
