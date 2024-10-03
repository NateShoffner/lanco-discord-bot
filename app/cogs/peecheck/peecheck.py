import os

import discord
from cogs.lancocog import LancoCog
from discord import Emoji
from discord.ext import commands
from PIL import Image


class PeeCheck(LancoCog, name="PeeCheck", description="PeeCheck cog"):

    colors = [
        "#FBFCEE",
        "#FAFAD5",
        "#F6F5B5",
        "#EDEE88",
        "#DFD969",
        "#DCC733",
        "#CFAE3B",
        "#B09435",
    ]

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.cache_dir = os.path.join(self.get_cog_data_directory(), "Cache")
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    @commands.Cog.listener()
    async def on_ready(self):
        await self.setup_emojis()

    @commands.command(name="peecheck", description="Mark your pee clarity")
    async def peecheck(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Pee Check",
            description="How clear is your pee?",
            color=discord.Color.yellow(),
        )
        msg = await ctx.send(embed=embed)
        emojis = await self.get_emojis()
        for emoji in emojis:
            await msg.add_reaction(emoji)

    def get_emoji_names(self) -> list[str]:
        emoji_prefix = "peecheck_"
        total_emojis = len(self.colors)
        return [f"{emoji_prefix}{i+1}" for i in range(total_emojis)]

    async def get_emojis(self) -> list[Emoji]:
        emojis = await self.bot.fetch_application_emojis()
        pc_emojis = [emoji for emoji in emojis if emoji.name.startswith("peecheck_")]
        pc_emojis.sort(key=lambda x: x.name)
        return pc_emojis

    async def setup_emojis(self):
        emoji_names = self.get_emoji_names()
        application_emojis = await self.bot.fetch_application_emojis()
        for emoji_name in emoji_names:
            if emoji_name not in [emoji.name for emoji in application_emojis]:
                self.logger.info(f"Emoji {emoji_name} not found. Creating...")
                color = self.colors.pop(0)
                await self.create_emoji(color, emoji_name)
            else:
                self.logger.info(f"Emoji {emoji_name} found")

    async def create_emoji(self, color: str, name: str):
        self.logger.info(f"Creating emoji {name} with color {color}")
        img = Image.new("RGB", (32, 32), color)
        filename = os.path.join(self.cache_dir, f"{name}.png")
        img.save(filename)

        with open(filename, "rb") as f:
            await self.bot.create_application_emoji(name=name, image=f.read())


async def setup(bot):
    await bot.add_cog(PeeCheck(bot))
