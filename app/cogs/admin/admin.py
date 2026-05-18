import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from utils.command_utils import is_bot_owner_or_admin


class Admin(LancoCog, name="Admin", description="Administrative commands"):
    g = app_commands.Group(name="admin", description="Administrative commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    @commands.command(name="delete", description="Delete a message")
    @is_bot_owner_or_admin()
    async def delete(self, ctx: commands.Context):
        """Delete a message"""
        # delete the message that was replied to
        message = ctx.message.reference.resolved
        await message.delete()
        # delete the command message
        await ctx.message.delete()

    @g.command(name="delete", description="Delete a message by ID")
    @is_bot_owner_or_admin()
    async def delete_by_id(self, interaction: discord.Interaction, message_id: str):
        """Delete a message by ID"""
        try:
            message_id = int(message_id)
        except ValueError:
            await interaction.response.send_message(
                "Invalid message ID.", ephemeral=True
            )
            return
        channel = interaction.channel
        try:
            message = await channel.fetch_message(message_id)
            await message.delete()
            await interaction.response.send_message(
                f"Message {message_id} deleted.", ephemeral=True
            )
        except discord.NotFound:
            await interaction.response.send_message(
                f"Message {message_id} not found.", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I do not have permission to delete messages in this channel.",
                ephemeral=True,
            )


async def setup(bot):
    await bot.add_cog(Admin(bot))
