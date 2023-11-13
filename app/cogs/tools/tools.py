import discord
from discord.ext import commands
from sys import version_info as sysv


class Tools(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='ping')
    async def ping(self, ctx):
        await ctx.send(f'🏓 {round(self.bot.latency * 1000)} ms.')

    @commands.command(name='status')
    async def status(self, ctx):
        embed = discord.Embed(title = 'Status', description='Bot Status', color = 0x00ff00)
        embed.add_field(name = 'Python', value = f'{sysv.major}.{sysv.minor}.{sysv.micro}')
        embed.add_field(name = 'Discord.py', value = f'{discord.__version__}')
        embed.add_field(name = 'Guilds', value = f'{len(self.bot.guilds)}')
        embed.add_field(name = 'Users', value = f'{len(self.bot.users)}')
        embed.add_field(name = 'Commands', value = f'{len(self.bot.commands)}')
        embed.add_field(name = 'Cogs', value = f'{len(self.bot.cogs)}')
        embed.add_field(name = 'Latency', value = f'{round(self.bot.latency * 1000)}ms')
        embed.add_field(name = 'Invite', value = f'[Invite Link](https://discord.com/api/oauth2/authorize?client_id={self.bot.user.id}&permissions=8&scope=bot)')
        embed.set_footer(text = f'©{self.bot.user.name}#{self.bot.user.discriminator} | {self.bot.user.id}')

        await ctx.send(embed = embed)

async def setup(bot):
    await bot.add_cog(Tools(bot))