import os
from wsgiref import headers

import aiohttp
import discord
from cogs.lancocog import LancoCog
from discord.ext import commands
from utils.file_downloader import FileDownloader


class TraceMoe(
    LancoCog, name="TraceMoe", description="Get the anime from a screenshot"
):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.cache_dir = os.path.join(self.get_cog_data_directory(), "Cache")
        self.file_downloader = FileDownloader()
        # self.register_context_menu(
        #    name="Sauce", callback=self.ctx_menu, errback=self.ctx_menu_error
        # )

    """
    async def ctx_menu(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        await interaction.channel.typing()
        embed = await self.process_sauce(message)
        await interaction.response.send_message(embed=embed)

    async def ctx_menu_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        await interaction.response.send_message("An error occurred", ephemeral=True)
    """

    async def process_sauce(self, message: discord.Message) -> discord.Embed:
        download = await self.file_downloader.download_attachments(
            message, self.cache_dir
        )

        if not download or len(download) == 0:
            self.logger.error("No files downloaded")
            return

        result = await self.send_trace_moe_request(download[0].filename)

        if result:
            similarity = result["similarity"]

            if similarity <= 0.85:
                self.logger.info(f"Similarity too low: {similarity}")
                embed = discord.Embed(title="Sauce")
                embed.description = "No anime found"
                return embed

            embed = discord.Embed(title="Sauce")

            minutes = int(result["from"] // 60)
            seconds = int(result["from"] % 60)

            embed.add_field(
                name="Title",
                value=result["anilist"]["title"]["romaji"],
                inline=False,
            )
            embed.add_field(name="Episode", value=result["episode"], inline=True)
            # mm:ss format
            embed.add_field(
                name="Time", value=f"{minutes:02}:{seconds:02}", inline=True
            )
            embed.add_field(
                name="Similarity",
                value=f"{result['similarity']:.2%}",
                inline=True,
            )
            embed.add_field(
                name="Anilist",
                value=f"https://anilist.co/anime/{result['anilist']['id']}",
                inline=False,
            )
            embed.add_field(
                name="MyAnimeList",
                value=f"https://myanimelist.net/anime/{result['anilist']['idMal']}",
                inline=False,
            )
        else:
            embed = discord.Embed(title="No sauce found")
            embed.description = result["error"]
        return embed

    @commands.command(name="sauce", description="Get the anime from a screenshot")
    async def tracemoe(self, ctx: commands.Context):
        if not ctx.message.reference:
            await ctx.send("Please reply to a message with an image")
        message = await ctx.fetch_message(ctx.message.reference.message_id)
        embed = await self.process_sauce(message)
        await ctx.send(embed=embed)

    async def send_trace_moe_request(self, filename):
        url = "https://api.trace.moe/search?anilistInfo"
        with open(filename, "rb") as f:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=f) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data["error"]:
                            self.logger.error(data["error"])
                            return None
                        return data["result"][
                            0
                        ]  # TODO handle multiple results with passable similarity


async def setup(bot):
    await bot.add_cog(TraceMoe(bot))
