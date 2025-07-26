import mimetypes
import os

import discord
from cogs.lancocog import LancoCog
from discord.ext import commands
from pydantic import BaseModel, Field
from pydantic_ai import Agent, BinaryContent
from utils.file_downloader import FileDownloader
from utils.tracked_message import track_message_ids


class ImageDetails(BaseModel):
    is_hotdog: bool = Field(
        ...,
        description="Indicates whether the image is a hotdog or not.",
    )

    is_pretending_to_be_hotdog: bool = Field(
        ...,
        description="Indicates whether the image is pretending to be a hotdog.",
    )

    reasoning: str = Field(
        ...,
        description="The reasoning behind the classification of the image.",
    )


class HotDog(LancoCog, name="HotDog", description="Profile Glizzies"):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.register_context_menu(
            name="Hot Dog", callback=self.ctx_menu, errback=self.ctx_menu_error
        )
        self.agent = Agent(
            model="openai:gpt-4o",
            system_prompt="Describe this image.",
            output_type=ImageDetails,
        )
        self.cache_dir = os.path.join(self.get_cog_data_directory(), "Cache")
        self.file_downloader = FileDownloader()

    async def ctx_menu(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        await self.send_description(interaction, message)

    async def ctx_menu_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        self.logger.error(error)
        await interaction.edit_original_response(
            content="An error occurred while processing the request."
        )

    @track_message_ids()
    async def send_description(
        self, ctx: commands.Context, message: discord.Message
    ) -> discord.Message:
        embed = discord.Embed(
            title="Performing Hot Dog Analysis",
            description="Please wait while we analyze the image for hotdog characteristics.",
            color=discord.Color.yellow(),
        )

        # check if context is an interaction
        if isinstance(ctx, discord.Interaction):
            await ctx.response.send_message(embed=embed)
            msg = await ctx.original_response()
        else:
            msg = await ctx.send(embed=embed)

        await ctx.channel.typing()
        details = await self.get_attachment_details(message)

        response = ""

        if details.is_hotdog:
            response += "This is a hotdog! 🌭"
            embed.title = "Hotdog Analysis Result"
            embed.color = discord.Color.green()
        elif details.is_pretending_to_be_hotdog:
            response += "This image is pretending to be a hotdog! 🤥🌭"
            embed.title = "Hotdog Analysis Result"
            embed.color = discord.Color.red()
        else:
            response += "This is NOTdog! 🚫🌭"
            embed.title = "Hotdog Analysis Result"
            embed.color = discord.Color.red()

        response += f"\n\n**Reasoning:** {details.reasoning}"

        embed.description = response
        await msg.edit(embed=embed)
        return msg

    async def get_attachment_details(self, message: discord.Message) -> ImageDetails:
        results = await self.file_downloader.download_attachments(
            message, self.cache_dir
        )

        if not results:
            return None

        filename = results[0].filename

        with open(filename, "rb") as f:
            image_bytes = f.read()

        # TODO might want to use python-magic so it's content-based
        mime_type, _ = mimetypes.guess_type(filename)

        if mime_type is None or not mime_type.startswith("image/"):
            raise ValueError("The provided file is not a valid image.")

        result = await self.agent.run(
            [
                BinaryContent(data=image_bytes, media_type=mime_type),
            ]
        )

        # cleanup
        for r in results:
            os.remove(r.filename)

        return result.output

    @commands.command(name="hotdog", description="Is this a hotdog?")
    async def hotdog(self, ctx: commands.Context):
        ref_message = ctx.message.reference
        if ref_message is None:
            await ctx.send("Please reply to a message with an image to analyze.")
            return
        await self.send_description(ctx, ref_message.resolved)


async def setup(bot):
    await bot.add_cog(HotDog(bot))
