import os

import discord
from cogs.lancocog import LancoCog
from discord import Emoji
from discord.ext import commands
from PIL import Image

from app.utils.emoji_uploader import EmojiUploader, LocalEmoji


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

    prefix = "peecheck_"

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.cache_dir = os.path.join(self.get_cog_data_directory(), "Cache")
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        self.emoji_uploader = EmojiUploader(bot)

    @commands.Cog.listener()
    async def on_ready(self):
        emoji_names = [f"{self.prefix}{i+1}" for i in range(len(self.colors))]
        local_emojis = [
            LocalEmoji(path=os.path.join(self.cache_dir, f"{name}.png"), name=name)
            for name in emoji_names
        ]

        for emoji in local_emojis:
            self.logger.info(f"Creating local emoji file {emoji.path}")
            color = self.colors.pop(0)
            img = Image.new("RGB", (32, 32), color)
            img.save(emoji.path)

        self.logger.info("Setting up PeeCheck emojis")
        await self.emoji_uploader.setup_emojis(local_emojis, force_update=False)

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

    async def get_emojis(self) -> list[Emoji]:
        emojis = await self.bot.fetch_application_emojis()
        pc_emojis = [emoji for emoji in emojis if emoji.name.startswith(self.prefix)]
        pc_emojis.sort(key=lambda x: x.name)
        return pc_emojis


async def setup(bot):
    await bot.add_cog(PeeCheck(bot))
