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
        super().__init__(bot)
        self.bot = bot
        self.bot.database.create_tables([CustomCommands])

    @commands_group.command(name="create", description="Create a custom command")
    @commands.has_permissions(administrator=True)
    @commands.is_owner()
    async def create(
        self,
        interaction: discord.Interaction,
        command_name: str,
        command_response: str,
        channel: discord.TextChannel = None,
    ):
        if CustomCommands.get_or_none(
            guild_id=interaction.guild_id, command_name=command_name.lower()
        ):
            await interaction.response.send_message(
                f"Command {command_name} already exists", ephemeral=True
            )
            return

        command = CustomCommands.create(
            guild_id=interaction.guild_id,
            command_name=command_name.lower(),
            command_response=command_response,
            channel_id=channel.id if channel else None,
        )

        await interaction.response.send_message(f"Created command {command_name}")

    @commands_group.command(name="delete", description="Delete a custom command")
    @commands.has_permissions(administrator=True)
    @commands.is_owner()
    async def delete(
        self,
        interaction: discord.Interaction,
        command_name: str,
        channel: discord.TextChannel = None,
    ):
        command = CustomCommands.get(
            guild_id=interaction.guild_id,
            command_name=command_name.lower(),
            channel_id=channel.id if channel else None,
        )
        if not command:
            await interaction.response.send_message(
                f"Command {command_name} does not exist", ephemeral=True
            )
            return
        command.delete_instance()
        await interaction.response.send_message(f"Deleted command {command_name}")

    @commands_group.command(name="edit", description="Edit a custom command")
    @commands.has_permissions(administrator=True)
    @commands.is_owner()
    async def edit(
        self, interaction: discord.Interaction, command_name: str, command_response: str
    ):
        command = CustomCommands.get_or_none(
            guild_id=interaction.guild_id, command_name=command_name.lower()
        )

        if not command:
            await interaction.response.send_message(
                f"Command {command_name} does not exist", ephemeral=True
            )
            return

        command.command_response = command_response
        command.save()

        await interaction.response.send_message(f"Edited command {command_name}")

    @commands_group.command(name="list", description="List all custom commands")
    async def list(self, interaction: discord.Interaction):
        commands = CustomCommands.select().where(
            CustomCommands.guild_id == interaction.guild_id
        )

        if not commands:
            await interaction.response.send_message("No commands found")
            return

        # TODO pagination
        embed = discord.Embed(title="Custom commands for this server")
        embed.description = "\n".join(
            f"{i+1}: {command.command_name}" for i, command in enumerate(commands)
        )

        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # TODO commands should perhaps be registered within the bot, but this works for now

        if message.author.bot:
            return

        if isinstance(message.channel, discord.DMChannel):
            return

        if message.content.startswith(self.bot.command_prefix):
            command_name = message.content[len(self.bot.command_prefix) :]
            command = CustomCommands.get_or_none(
                guild_id=message.guild.id, command_name=command_name.lower()
            )

            if command:
                if (
                    command.channel_id is not None
                    and command.channel_id != message.channel.id
                ):
                    return

                await message.channel.send(command.command_response)


async def setup(bot):
    await bot.add_cog(Commands(bot))
