import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from reactionmenu import ReactionButton, ReactionMenu
from utils.command_utils import is_bot_owner_or_admin
from utils.tracked_message import track_message_ids

from .models import CustomCommands


class Commands(LancoCog, name="Commands", description="Custom guild commands"):
    commands_group = app_commands.Group(
        name="commands",
        description="Custom commands commands so you can command commands with commands",
    )

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot.database.create_tables([CustomCommands])

    @commands_group.command(name="create", description="Create a custom command")
    @is_bot_owner_or_admin()
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
            embed = discord.Embed(
                title="Command already exists",
                description=f"Command {command_name} already exists",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        command_response = self.format_message_response(command_response)

        command = CustomCommands.create(
            guild_id=interaction.guild_id,
            command_name=command_name.lower(),
            command_response=command_response,
            channel_id=channel.id if channel else None,
        )

        embed = discord.Embed(
            title="Command created",
            description=f"Command {command_name} created",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="Command response",
            value=command_response,
            inline=False,
        )
        if channel:
            embed.add_field(
                name="Channel",
                value=channel.mention,
                inline=False,
            )
        await interaction.response.send_message(embed=embed)

    @commands_group.command(name="delete", description="Delete a custom command")
    @is_bot_owner_or_admin()
    async def delete(
        self,
        interaction: discord.Interaction,
        command_name: str,
        channel: discord.TextChannel = None,
    ):
        command = CustomCommands.get_or_none(
            guild_id=interaction.guild_id,
            command_name=command_name.lower(),
            channel_id=channel.id if channel else None,
        )
        if not command:
            embed = discord.Embed(
                title="Command not found",
                description=f"Command {command_name} not found",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        command.delete_instance()

        embed = discord.Embed(
            title="Command deleted",
            description=f"Command {command_name} deleted",
            color=discord.Color.red(),
        )

        await interaction.response.send_message(embed=embed)

    @commands_group.command(name="edit", description="Edit a custom command")
    @is_bot_owner_or_admin()
    async def edit(
        self, interaction: discord.Interaction, command_name: str, command_response: str
    ):
        command = CustomCommands.get_or_none(
            guild_id=interaction.guild_id, command_name=command_name.lower()
        )

        if not command:
            embed = discord.Embed(
                title="Command not found",
                description=f"Command {command_name} not found",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        command_response = self.format_message_response(command_response)
        command.command_response = command_response
        command.save()

        embed = discord.Embed(
            title="Command edited",
            description=f"Command {command_name} edited",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="Command response",
            value=command_response,
            inline=False,
        )
        await interaction.response.send_message(embed=embed)

    @commands_group.command(name="list", description="List all custom commands")
    async def list(self, interaction: discord.Interaction):
        commands = CustomCommands.select().where(
            CustomCommands.guild_id == interaction.guild_id
        )

        if not commands:
            embed = discord.Embed(
                title="No commands found",
                description="No commands found",
                color=discord.Color.red(),
            )

            await interaction.response.send_message(embed=embed)
            return

        menu = ReactionMenu(interaction, menu_type=ReactionMenu.TypeEmbed)

        COMMANDS_PER_PAGE = 8
        commands = list(commands)
        commands.sort(key=lambda x: x.command_name)

        prefix = self.bot.command_prefix

        for i in range(0, len(commands), COMMANDS_PER_PAGE):
            page_commands = commands[i : i + COMMANDS_PER_PAGE]

            embed = discord.Embed(
                title=f"Custom commands for {interaction.guild.name}: {len(commands)}"
            )

            for command in page_commands:
                command_value = command.command_response

                if command.channel_id:
                    channel = self.bot.get_channel(command.channel_id)
                    if channel:
                        command_value += f"\n(Only available in {channel.mention})"

                embed.add_field(
                    name=f"{prefix}{command.command_name}",
                    value=command_value,
                    inline=False,
                )

            menu.add_page(embed)

        if len(commands) > COMMANDS_PER_PAGE:
            menu.add_button(ReactionButton.go_to_first_page())
            menu.add_button(ReactionButton.back())
            menu.add_button(ReactionButton.next())
            menu.add_button(ReactionButton.go_to_page())
            menu.add_button(ReactionButton.go_to_last_page())

        menu.add_button(ReactionButton.end_session())

        await menu.start()

    @commands.Cog.listener()
    @track_message_ids()
    async def on_message(self, message: discord.Message) -> discord.Message:
        # TODO commands should perhaps be registered within the bot, but this works for now

        if message.author.bot:
            return None

        if isinstance(message.channel, discord.DMChannel):
            return None

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

                return await message.channel.send(command.command_response)

    def format_message_response(self, message: str) -> str:
        """Format the message to allow for newlines and other formatting"""
        response = message.replace("\\n", "\n")
        return response


async def setup(bot):
    await bot.add_cog(Commands(bot))
