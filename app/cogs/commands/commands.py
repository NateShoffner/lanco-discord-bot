import discord
from discord.ext import commands
from discord import app_commands
from .models import CustomCommands

from cogs.lancocog import LancoCog


class Commands(LancoCog):
    commands_group = app_commands.Group(
        name="commands",
        description="Custom commands commands so you can command commands with commands",
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.bot.database.create_tables([CustomCommands])

    @commands.Cog.listener()
    async def on_ready(self):
        print("Commands cog loaded")
        await super().on_ready()

    @commands_group.command(name="create", description="Create a custom command")
    @commands.has_permissions(administrator=True)
    @commands.is_owner()
    async def create(
        self, interaction: discord.Interaction, command_name: str, command_response: str
    ):
        if CustomCommands.get_or_none(
            guild_id=interaction.guild_id, command_name=command_name
        ):
            await interaction.response.send_message(
                f"Command {command_name} already exists", ephemeral=True
            )
            return

        command = CustomCommands.create(
            guild_id=interaction.guild_id,
            command_name=command_name,
            command_response=command_response,
        )

        await interaction.response.send_message(
            f"Created command {command_name}", ephemeral=True
        )

    @commands_group.command(name="delete", description="Delete a custom command")
    @commands.has_permissions(administrator=True)
    @commands.is_owner()
    async def delete(self, interaction: discord.Interaction, command_name: str):
        command = CustomCommands.get(
            guild_id=interaction.guild_id, command_name=command_name
        )
        command.delete_instance()

        await interaction.response.send_message(
            f"Deleted command {command_name}", ephemeral=True
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # TODO commands should perhaps be registered within the bot, but this works for now

        if message.author.bot:
            return

        if message.content.startswith(self.bot.command_prefix):
            command_name = message.content[len(self.bot.command_prefix) :]
            command = CustomCommands.get_or_none(
                guild_id=message.guild.id, command_name=command_name
            )

            if command:
                await message.channel.send(command.command_response)


async def setup(bot):
    await bot.add_cog(Commands(bot))
