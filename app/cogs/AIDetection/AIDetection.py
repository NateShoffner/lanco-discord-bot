"""
AIDetection Cog

Description:
Analyze images and videos for AI-generated content.
"""

import os

import discord
from cogs.lancocog import LancoCog
from discord import Emoji
from discord.ext import commands
from sightengine.client import SightEngineClient
from sightengine.models import CheckRequest, CheckResponse
from utils.emoji_uploader import EmojiUploader, LocalEmoji
from utils.file_downloader import FileDownloader
from utils.progressbar_generator import ProgressEmoteGenerator
from utils.tracked_message import track_message_ids


class AIDetection(
    LancoCog,
    name="AIDetection",
    description="Analyze images and videos for AI-generated content.",
):
    progress_bar_emoji_prefix = "pb_"

    def __init__(self, bot):
        super().__init__(bot)
        self.client = SightEngineClient(
            api_user=os.getenv("SIGHTENGINE_API_USER"),
            api_secret=os.getenv("SIGHTENGINE_API_SECRET"),
        )
        self.cache_dir = os.path.join(self.get_cog_data_directory(), "Cache")
        self.file_downloader = FileDownloader()
        self.register_context_menu(
            name="Analyze", callback=self.ctx_menu, errback=self.ctx_menu_error
        )
        self.progress_emote_generator = ProgressEmoteGenerator(
            output_dir=self.cache_dir
        )

    @commands.Cog.listener()
    async def on_ready(self):
        # setup progress bar emojis
        ss = self.progress_emote_generator.generate_sprite_set()
        local_emojis = [
            LocalEmoji(path=str(path), name=f"{self.progress_bar_emoji_prefix}{key}")
            for key, path in ss.items()
        ]

        self.logger.info("Setting up progress bar emojis")
        emoji_uploader = EmojiUploader(self.bot)
        await emoji_uploader.setup_emojis(local_emojis, force_update=False)

    async def get_pb_emojis(self, parts_we_need: list[str]) -> list[Emoji]:
        """Get progress bar emojis by their names"""
        emojis = await self.bot.fetch_application_emojis()
        pb_emojis = [
            emoji
            for emoji in emojis
            if emoji.name.startswith(self.progress_bar_emoji_prefix)
        ]
        pb_emojis_dict = {emoji.name: emoji for emoji in pb_emojis}
        return [
            pb_emojis_dict[part] for part in parts_we_need if part in pb_emojis_dict
        ]

    async def ctx_menu(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        await self.send_analysis(interaction, message)

    async def ctx_menu_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        self.logger.error(error)
        await interaction.edit_original_response(
            content="An error occurred while processing the request."
        )

    async def get_attachment_details(self, message: discord.Message) -> CheckResponse:
        results = await self.file_downloader.download_attachments(
            message, self.cache_dir
        )

        if not results:
            return None

        filename = results[0].filename

        params = {"opt_generators": "on"}

        request = CheckRequest(
            models=[
                "genai",
                "deepfake",
            ],
            file=filename,
            params=params,
        )

        response = await self.client.check(request)
        return response

    async def build_response_embed(self, response: CheckResponse) -> discord.Embed:
        embed = discord.Embed(
            title="AI Detection Results",
            color=discord.Color.blue(),
        )

        if not response:
            embed.add_field(
                name="Error", value="No response from SightEngine.", inline=False
            )
            return embed

        for gen in response.type.ai_generators.items():
            gen_name = gen[0]
            percent = gen[1] * 100  # Convert from 0.001 to 0.1% etc.

            if percent <= 0.1:
                continue

            emoji_names = {
                key: f"{self.progress_bar_emoji_prefix}{key}"
                for key in self.progress_emote_generator.emoji_names.keys()
            }

            bar_parts = self.progress_emote_generator.percentage_to_bar_parts(
                percent=percent, segments=10, emoji_markup=emoji_names
            )

            pb_emojis = await self.get_pb_emojis(bar_parts)
            pb_msg = "".join(str(e) for e in pb_emojis)

            embed.add_field(
                name=f"{gen_name}", value=f"{pb_msg} {percent:.2f}%", inline=False
            )

        return embed

    @track_message_ids()
    async def send_analysis(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> discord.Message:
        await interaction.response.send_message("Processing the file...")
        await interaction.channel.typing()
        response = await self.get_attachment_details(message)
        embed = await self.build_response_embed(response)
        msg = await interaction.edit_original_response(embed=embed)
        return msg


async def setup(bot):
    await bot.add_cog(AIDetection(bot))
