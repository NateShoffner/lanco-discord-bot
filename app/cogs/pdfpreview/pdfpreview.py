import os

import discord
import fitz
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from utils.command_utils import is_bot_owner_or_admin
from utils.file_downloader import FileDownloader
from utils.viruscheck import VirusCheck, VirusTotalResults

from .models import PDFPreviewConfig


class PDFPreview(
    LancoCog, name="PDFPreview", description="Generates a preview of a PDF file"
):
    pdf_group = app_commands.Group(name="pdf", description="PDF Preview Commands")

    # Discord renders at most 4 images in a single multi-embed gallery, so
    # there's no point generating more page previews than that.
    MAX_PREVIEW_PAGES = 4

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.cache_dir = os.path.join(self.get_cog_data_directory(), "Cache")
        self.previews_path = os.path.join(self.get_cog_data_directory(), "Previews")
        self.virus_check = VirusCheck(os.getenv("VIRUS_TOTAL_API_KEY"))
        if not os.path.exists(self.previews_path):
            os.makedirs(self.previews_path)
        self.bot.database.create_tables([PDFPreviewConfig])
        self.file_downloader = FileDownloader()

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
        pdf_url = None

        if pdf_atts:
            results = await self.file_downloader.download_attachments(
                message, self.cache_dir
            )
            pdf_filename = results[0].filename
            pdf_url = pdf_atts[0]
        elif pdf_links:
            pdf_filename = await self.file_downloader.download_file(
                pdf_links[0], self.cache_dir
            )
            pdf_url = pdf_links[0]

        if not pdf_filename:
            return

        preview_pages = max(1, pdf_preview_config.preview_pages)

        file_size = os.path.getsize(pdf_filename)
        image_paths, page_count = self.generate_pdf_preview(pdf_filename, preview_pages)

        files = [
            discord.File(path, filename=os.path.basename(path)) for path in image_paths
        ]
        embeds = self.build_preview_embeds(image_paths, page_count, file_size, pdf_url)

        embed_msg = await message.channel.send(files=files, embeds=embeds)

        vt_results = await self.virus_check.check_file(pdf_filename)
        # update the embeds with the VirusTotal results
        embeds = self.build_preview_embeds(
            image_paths, page_count, file_size, pdf_url, vt_results
        )
        await embed_msg.edit(embeds=embeds)

    def generate_pdf_preview(self, pdf_path: str, preview_pages: int = 1):
        """Render the first ``preview_pages`` pages of the PDF to PNGs.

        Returns a tuple of (list of image paths, total page count). The number
        of pages rendered is capped by both the PDF's page count and
        ``MAX_PREVIEW_PAGES`` (Discord renders at most 4 gallery images).
        """
        pdf_filename = os.path.basename(pdf_path)
        base_name = pdf_filename.replace(".pdf", "")

        pdf_document = fitz.open(pdf_path)
        page_count = pdf_document.page_count

        pages_to_render = min(preview_pages, page_count, self.MAX_PREVIEW_PAGES)

        image_paths = []
        for page_number in range(pages_to_render):
            page = pdf_document.load_page(page_number)
            pix = page.get_pixmap()
            image_path = os.path.join(
                self.previews_path, f"{base_name}_page{page_number + 1}.png"
            )
            pix.save(image_path)
            image_paths.append(image_path)

        return (image_paths, page_count)

    def build_preview_embeds(
        self,
        image_paths: list[str],
        page_count: int,
        file_size: int,
        pdf_url: str,
        vt_results: VirusTotalResults = None,
    ):
        """Build a list of embeds that Discord renders as a single gallery.

        Multiple embeds sharing the same ``url`` collapse into one embed with
        up to 4 images, so every embed is given the source PDF's URL. This
        doubles as the clickable link on the "PDF Preview" title. Metadata
        fields live on the first embed only.
        """
        embeds = []
        for index, image_path in enumerate(image_paths):
            filename = os.path.basename(image_path)
            embed = discord.Embed(url=pdf_url)

            if index == 0:
                embed.title = "PDF Preview"
                embed.add_field(name="Total Pages", value=page_count, inline=True)
                embed.add_field(
                    name="File Size",
                    value=f"{file_size / 1024 / 1024:.2f} MB",
                    inline=True,
                )

                if vt_results:
                    embed.color = (
                        discord.Color.green()
                        if vt_results.is_safe
                        else discord.Color.red()
                    )
                    vt_status = "✅ Safe" if vt_results.is_safe else "❌ Malicious"
                    embed.add_field(
                        name="VirusTotal Results",
                        value=f"[{vt_status}]({vt_results.url})",
                        inline=False,
                    )
                else:
                    embed.add_field(
                        name="VirusTotal Results", value="⏳ Pending", inline=False
                    )

            embed.set_image(url=f"attachment://{filename}")
            embeds.append(embed)

        return embeds

    @pdf_group.command(
        name="toggle",
        description="Toggle PDF Preview for this server",
    )
    @is_bot_owner_or_admin()
    async def toggle(self, interaction: discord.Interaction):
        config, created = PDFPreviewConfig.get_or_create(guild_id=interaction.guild.id)
        # Toggle the enabled flag without dropping the row so per-guild
        # settings (e.g. preview_pages) persist across toggles.
        config.enabled = created or not config.enabled
        config.save()
        await interaction.response.send_message(
            "PDF Preview enabled" if config.enabled else "PDF Preview disabled"
        )

    @pdf_group.command(
        name="pages",
        description="Set how many pages (1-4) to include in PDF previews",
    )
    @app_commands.describe(pages="Number of pages to preview (1-4)")
    @is_bot_owner_or_admin()
    async def pages(self, interaction: discord.Interaction, pages: int):
        if pages < 1 or pages > self.MAX_PREVIEW_PAGES:
            await interaction.response.send_message(
                f"Please choose a value between 1 and {self.MAX_PREVIEW_PAGES}.",
                ephemeral=True,
            )
            return

        config, _ = PDFPreviewConfig.get_or_create(guild_id=interaction.guild.id)
        config.preview_pages = pages
        config.save()
        await interaction.response.send_message(
            f"PDF previews will now show the first {pages} page(s)."
        )


async def setup(bot):
    await bot.add_cog(PDFPreview(bot))
