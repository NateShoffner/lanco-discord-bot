from dataclasses import dataclass

import aiohttp
import discord
from cogs.lancocog import LancoCog
from discord.ext import commands


@dataclass
class SpyBot:
    id: str
    username: str
    avatar: str
    discriminator: int
    public_flags: int
    flags: int
    banner: None
    accent_color: None
    global_name: None


class SpyDotKick(LancoCog, name="SpyDotKick", description="Check for loser bots"):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    @commands.command(name="botcheck", description="Check for loser bots")
    async def botcheck(self, ctx: commands.Context, guild_id: int = None):
        if guild_id is None:
            guild_id = ctx.guild.id

        guild = self.bot.get_guild(guild_id)

        bots = await self.get_bots(guild_id)

        embed = discord.Embed(title="Bot Check")

        if len(bots) == 0:
            embed.description = "No bots found"
            embed.color = discord.Color.green()
        else:
            embed.description = (
                f"{len(bots)} bots found\n\n{', '.join([bot.mention for bot in bots])}"
            )
            embed.color = discord.Color.red()

        await ctx.send(embed=embed)

    async def get_bots(self, server_id: int) -> list[discord.User]:
        url = "https://kickthespy.pet/getBot?id="
        url += str(server_id)
        bots = []
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                bot_data = await response.json()

                if bot_data.get("error") is not None:
                    return bots

                id = int(bot_data["id"])
                user = self.bot.get_user(id)
                if user is not None:
                    bots.append(user)
        return bots


async def setup(bot):
    await bot.add_cog(SpyDotKick(bot))
