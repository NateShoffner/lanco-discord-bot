from cogs.lancocog import LancoCog
from discord.ext import commands
from utils.command_utils import is_bot_owner_or_admin


class Admin(LancoCog, name="Admin", description="Admin cog"):

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    @commands.command(name="delete", description="Delete a message")
    @is_bot_owner_or_admin()
    async def delete(self, ctx: commands.Context):
        # delete the message that was replied to
        message = ctx.message.reference.resolved
        await message.delete()
        # delete the command message
        await ctx.message.delete()


async def setup(bot):
    await bot.add_cog(Admin(bot))
