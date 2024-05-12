import discord
from cogs.lancocog import LancoCog
from discord.ext import commands
from jikanpy import Jikan
from numpy import True_


class Anime(LancoCog, name="Anime", description="Anime commands"):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.jikan = Jikan()

    @commands.command(name="anime", description="Get anime information")
    async def anime(self, ctx: commands.Context, *, title: str):
        anime = self.jikan.search("anime", title)
        print(anime)
        if not anime:
            await ctx.send("No anime found")
            return
        anime = anime["data"][0]
        embed = self.build_anime_embed(anime)
        await ctx.send(embed=embed)

    def build_anime_embed(self, anime):
        embed = discord.Embed(title=anime["title"])

        embed.set_thumbnail(url=anime["images"]["jpg"]["image_url"])
        embed.add_field(name="Type", value=anime["type"], inline=True)
        embed.add_field(name="Episodes", value=anime["episodes"], inline=True)
        embed.add_field(name="Score", value=anime["score"], inline=True)
        embed.add_field(name="URL", value=anime["url"], inline=True)
        return embed


async def setup(bot):
    await bot.add_cog(Anime(bot))
