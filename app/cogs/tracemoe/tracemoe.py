import os
import uuid
from wsgiref import headers
import aiohttp
import discord
from discord.ext import commands
import urllib3
from cogs.lancocog import LancoCog


class TraceMoe(LancoCog):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.cache_dir = os.path.join(self.get_cog_data_directory(), "Cache")

    # repond when user replies and uses the command
    @commands.command(name="sauce", description="Get the anime from a screenshot")
    async def tracemoe(self, ctx: commands.Context):
        if not ctx.message.reference:
            await ctx.send("Please reply to a message with an image")

        message = await ctx.fetch_message(ctx.message.reference.message_id)

        url = None
        if message.attachments:
            self.logger.info("Attachment found in message")
            attachment = message.attachments[0]
            url = attachment.url
            ext = url.split(".")[-1].split("?")[0]
        elif message.embeds:
            self.logger.info("Embed found in message")
            embed = message.embeds[0]

            if embed.image:
                url = embed.image.proxy_url
                ext = url.split(".")[-1].split("?")[0]
            if embed.video:
                proxy_url = embed.video.proxy_url

                self.logger.info(f"Proxy URL: {proxy_url}")

                if "tenor.com" in proxy_url:
                    # tenor seems to ignore the extension but instead uses the URL path to determine the file type

                    # gif
                    # https://media.tenor.com/jv1uzXK_ELwAAAAC/fullmetal-alchemist.gif
                    # mp4
                    # https://media.tenor.com/jv1uzXK_ELwAAAPo/fullmetal-alchemist.gif

                    # mp4
                    # https://media.tenor.com/M0DJo6-jF7AAAAPo/anime-responsibilities.mp4
                    # gif
                    # https://media.tenor.com/M0DJo6-jF7AAAAAC/anime-responsibilities.gif

                    # hacky way to get the original url and get the original GIF
                    # Ex: https://images-ext-2.discordapp.net/external/PHVkBmSMxJdxhSl2dlVt9_VL4tiHyn0blDb9ZBNWLjQ/https/media.tenor.com/M0DJo6-jF7AAAAPo/anime-responsibilities.mp4

                    # parse the proxy url and replace the extension, subdomain, and path
                    tenor_url = proxy_url.split("/https/")[1]
                    url_split = tenor_url.split("/")
                    path = url_split[1]
                    if path.endswith("Po"):
                        path = path[:-2] + "AC"
                    new_url = f"https://c.tenor.com/{path}/tenor.gif"
                    url = new_url

                    # https://media.tenor.com/jv1uzXK_ELwAAAPo/fullmetal-alchemist.mp4
                    # https://c.tenor.com/jv1uzXK_ELwAAAAC/tenor.gif
                    # https://c.tenor.com/jv1uzXK_ELwAAAC/fullmetal-alchemist.gif

                    ext = "gif"

            self.logger.info(f"URL: {url}")
        else:
            await ctx.send("Please reply to a message with an image")
            return

        # download the image
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.read()
                    random_uuid = uuid.uuid4()

                    if not os.path.exists(self.cache_dir):
                        os.makedirs(self.cache_dir)

                    filename = os.path.join(self.cache_dir, f"{random_uuid}.{ext}")
                    with open(filename, "wb") as f:
                        f.write(data)

                    result = await self.send_trace_moe_request(filename)

                    if result:
                        similarity = result["similarity"]

                        if similarity <= 0.85:
                            self.logger.info(f"Similarity too low: {similarity}")
                            embed = discord.Embed(title="Sauce")
                            embed.description = "No anime found"
                            await ctx.send(embed=embed)
                            return

                        embed = discord.Embed(title="Sauce")

                        minutes = int(result["from"] // 60)
                        seconds = int(result["from"] % 60)

                        embed.add_field(
                            name="Title",
                            value=result["anilist"]["title"]["romaji"],
                            inline=False,
                        )
                        embed.add_field(
                            name="Episode", value=result["episode"], inline=True
                        )
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
                        return data["result"][0] # TODO handle multiple results with passable similarity


async def setup(bot):
    await bot.add_cog(TraceMoe(bot))
