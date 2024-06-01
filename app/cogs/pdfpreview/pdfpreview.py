import base64
import os
from dataclasses import dataclass

import discord
import fitz
import vt
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from utils.command_utils import is_bot_owner_or_admin

from .models import PDFPreviewConfig


@dataclass
class VirusTotalResults:
    md5: str
    sha256: str
    url: str
    is_safe: bool


class PDFPreview(
    LancoCog, name="PDFPreview", description="Generates a preview of a PDF file"
):
    pdf_group = app_commands.Group(name="pdf", description="PDF Preview Commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.cache_dir = os.path.join(self.get_cog_data_directory(), "Cache")
        self.previews_path = os.path.join(self.get_cog_data_directory(), "Previews")
        if not os.path.exists(self.previews_path):
            os.makedirs(self.previews_path)
        self.bot.database.create_tables([PDFPreviewConfig])

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        pdf_preview_config = PDFPreviewConfig.get_or_none(guild_id=message.guild.id)

        if not pdf_preview_config or not pdf_preview_config.enabled:
            return

        pdf_atts = [
            attachment.url
            for attachment in message.attachments
            if attachment.filename.endswith(".pdf")
        ]
        # check for pdf links in the message content
        pdf_links = [word for word in message.content.split() if word.endswith(".pdf")]

        # TODO check for multiple pdfs in a single message

        if not pdf_links and not pdf_atts:
            return

        pdf_filename = None

        if pdf_atts:
            results = await self.download_attachments(message, self.cache_dir)
            pdf_filename = results[0].filename
        elif pdf_links:
            pdf_filename = await self.download_file(pdf_links[0], self.cache_dir)

        if not pdf_filename:
            return

        file_size = os.path.getsize(pdf_filename)
        image_path, page_count = self.generate_pdf_preview(pdf_filename)
        filename = os.path.basename(image_path)

        file = discord.File(image_path, filename=filename)
        embed = self.build_preview_embed(image_path, page_count, file_size)

        embed_msg = await message.channel.send(file=file, embed=embed)

        vt_results = await self.virus_check(pdf_filename)
        # update the embed with the VirusTotal results
        embed = self.build_preview_embed(image_path, page_count, file_size, vt_results)
        await embed_msg.edit(embed=embed)

    def generate_pdf_preview(self, pdf_path: str):
        pdf_filename = os.path.basename(pdf_path)
        image_filename = pdf_filename.replace(".pdf", ".png")
        image_path = os.path.join(self.previews_path, image_filename)

        pdf_document = fitz.open(pdf_path)
        first_page = pdf_document.load_page(0)
        pix = first_page.get_pixmap()
        pix.save(image_path)

        return (image_path, pdf_document.page_count)

    def build_preview_embed(
        self,
        image_path: str,
        page_count: int,
        file_size: int,
        vt_results: VirusTotalResults = None,
    ):
        filename = os.path.basename(image_path)

        embed = discord.Embed(title="PDF Preview")
        embed.add_field(name="Total Pages", value=page_count, inline=True)
        embed.add_field(
            name="File Size", value=f"{file_size / 1024 / 1024:.2f} MB", inline=True
        )

        if vt_results:
            embed.color = (
                discord.Color.green() if vt_results.is_safe else discord.Color.red()
            )
            vt_status = "✅ Safe" if vt_results.is_safe else "❌ Malicious"
            embed.add_field(
                name="VirusTotal Results",
                value=f"[{vt_status}]({vt_results.url})",
                inline=False,
            )
        else:
            embed.add_field(name="VirusTotal Results", value="⏳ Pending", inline=False)

        embed.set_image(url=f"attachment://{filename}")
        return embed

    async def virus_check(self, pdf_path: str) -> tuple:
        async with vt.Client(os.getenv("VIRUS_TOTAL_API_KEY")) as client:
            with open(pdf_path, "rb") as f:
                self.logger.info(f"Uploading {pdf_path}")
                analysis = await client.scan_file_async(f)
                self.logger.info(f"File {pdf_path} uploaded.")

                completed_analysis = await client.wait_for_analysis_completion(analysis)

                self.logger.info(f"{pdf_path}: {completed_analysis.stats}")

                # TODO probably a better way to obtain the sha256
                decoded = base64.b64decode(analysis.id).decode("utf-8")
                md5 = decoded.split(":")[0]
                file_details = await client.get_object_async("/files/" + md5)

                url = "https://www.virustotal.com/gui/file/" + file_details.sha256
                is_safe = completed_analysis.stats["malicious"] == 0

                return VirusTotalResults(md5, file_details.sha256, url, is_safe)

    @pdf_group.command(
        name="toggle",
        description="Toggle PDF Preview for this server",
    )
    @is_bot_owner_or_admin()
    async def toggle(self, interaction: discord.Interaction):
        config, created = PDFPreviewConfig.get_or_create(guild_id=interaction.guild.id)
        if created:
            config.enabled = True
            config.save()
            await interaction.response.send_message("PDF Preview enabled")
        else:
            config.delete_instance()
            await interaction.response.send_message("PDF Preview disabled")


async def setup(bot):
    await bot.add_cog(PDFPreview(bot))
