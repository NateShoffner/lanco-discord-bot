import discord
from cogs.lancocog import LancoCog
from discord import app_commands, ui
from discord.ext import commands
from pydantic import BaseModel, Field
from pydantic_ai import Agent, BinaryContent
from reactionmenu import ReactionButton, ReactionMenu
from utils.ai_utils import run_agent
from utils.apm import transaction as apm_transaction
from utils.command_utils import is_bot_owner_or_admin
from utils.tracked_message import track_message_ids

from .models import CustomCommands


class AICommandResponse(BaseModel):
    response: str = Field(
        ...,
        description="The AI-generated response for the command.",
    )


class CommandTypes:
    BASIC = "basic"
    AI = "ai"


class CommandModal(ui.Modal, title="Command Info"):
    command_name = ui.TextInput(
        label="Command Name:",
        style=discord.TextStyle.short,
        required=True,
    )

    type_selection = ui.Label(
        text="Select Command Type:",
        description=" Select the type of command.",
        component=ui.Select(
            placeholder="Choose command type",
            options=[
                discord.SelectOption(
                    label="Basic",
                    description="A basic custom command.",
                    value=CommandTypes.BASIC,
                    default=True,
                ),
                discord.SelectOption(
                    label="AI",
                    description="An AI-powered command.",
                    value=CommandTypes.AI,
                ),
            ],
            min_values=1,
            max_values=1,
            required=False,
        ),
    )

    channel_selection = ui.Label(
        text="Select Channel (Optional):",
        description=" Select a channel where this command can be used.",
        component=ui.ChannelSelect(
            channel_types=[discord.ChannelType.text], required=False
        ),
    )

    cooldown_selection = ui.Label(
        text="Set Cooldown (Optional):",
        description=" Set a cooldown for this command.",
        component=ui.Select(
            placeholder="Choose cooldown",
            options=[
                discord.SelectOption(label="10 seconds", value="10"),
                discord.SelectOption(label="30 seconds", value="30"),
                discord.SelectOption(label="1 minute", value="60"),
                discord.SelectOption(label="5 minutes", value="300"),
                discord.SelectOption(label="10 minutes", value="600"),
                discord.SelectOption(label="30 minutes", value="1800"),
                discord.SelectOption(label="1 hour", value="3600"),
            ],
            min_values=1,
            max_values=1,
            required=False,
        ),
    )

    command_response = ui.TextInput(
        label="Command Response/Prompt:",
        style=discord.TextStyle.long,
        required=True,
    )

    def __init__(self, command: CustomCommands = None):
        super().__init__(timeout=None)
        self.command = command
        if command:
            self.command_name.default = command.command_name
            self.command_response.default = command.command_response

            for option in self.type_selection.component.options:
                option.default = option.value == command.command_type

            if command.channel_id:
                self.channel_selection.component.default_values = [
                    discord.Object(id=command.channel_id)
                ]

            if command.cooldown:
                for option in self.cooldown_selection.component.options:
                    option.default = option.value == str(command.cooldown)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        edit = self.command is not None

        def format_message_response(message: str) -> str:
            """Format the message to allow for newlines and other formatting"""
            response = message.replace("\\n", "\n")
            return response

        config, created = CustomCommands.get_or_create(
            guild_id=interaction.guild_id,
            command_name=self.command_name.value.lower(),
        )

        config.command_response = format_message_response(self.command_response.value)
        config.command_type = self.type_selection.component.values[0]

        if self.channel_selection.component.values:
            config.channel_id = self.channel_selection.component.values[0].id
        else:
            config.channel_id = None

        if self.cooldown_selection.component.values:
            config.cooldown = int(self.cooldown_selection.component.values[0])
        else:
            config.cooldown = 0

        config.last_updated = discord.utils.utcnow()
        config.author = interaction.user.id
        config.save()

        embed_title = "Command Edited" if edit else "Command Created"
        embed = discord.Embed(title=embed_title, color=discord.Color.blue())
        embed.add_field(name="Command Name", value=self.command_name.value)
        embed.add_field(
            name="Command Response/Prompt", value=self.command_response.value
        )
        embed.add_field(
            name="Command Type", value=self.type_selection.component.values[0]
        )

        if self.channel_selection.component.values:
            channel_mention = self.channel_selection.component.values[0].mention
            embed.add_field(name="Channel", value=channel_mention)

        if self.cooldown_selection.component.values:
            cooldown_value = self.cooldown_selection.component.values[0]
            embed.add_field(name="Cooldown (seconds)", value=cooldown_value)

        await interaction.response.send_message(embed=embed, ephemeral=True)


class Commands(LancoCog, name="Commands", description="Custom guild commands"):
    commands_group = app_commands.Group(
        name="commands",
        description="Custom commands commands so you can command commands with commands",
    )

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot.database.create_tables([CustomCommands])
        self.agent = Agent(
            model="openai:gpt-5-nano",
            system_prompt="Generate a concise and relevant response based on the user's command prompt.",
            output_type=AICommandResponse,
        )

    @commands_group.command(name="create", description="Create a custom command")
    @is_bot_owner_or_admin()
    async def create2(self, interaction: discord.Interaction):
        modal = CommandModal()
        await interaction.response.send_modal(modal)

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
    async def edit(self, interaction: discord.Interaction, command_name: str):
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

        modal = CommandModal(command=command)
        await interaction.response.send_modal(modal)

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

        prefix = self.bot.get_guild_prefix(interaction.guild)

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

        prefix = self.bot.get_guild_prefix(message.guild)
        if message.content.startswith(prefix):
            command_name = message.content[len(prefix) :]
            command = CustomCommands.get_or_none(
                guild_id=message.guild.id, command_name=command_name.lower()
            )

            if command:
                if (
                    command.channel_id is not None
                    and command.channel_id != message.channel.id
                ):
                    return

                # TODO handle cooldowns
                # TODO handle exclusive owner

                self.logger.info(
                    f"Executing custom command '{command.command_name}' in guild '{message.guild.name}' ({message.guild.id}) by user '{message.author}' ({message.author.id})"
                )

                msg = None

                async with apm_transaction(
                    command.command_name,
                    "custom_command",
                    guild_id=message.guild.id,
                ):
                    if command.command_type == CommandTypes.AI:
                        await message.channel.typing()
                        response = await run_agent(
                            lambda: self.agent.run(command.command_response),
                            message.channel.send,
                        )
                        if response is None:
                            return

                        # limit it for a discord message
                        if len(response.output.response) > 2000:
                            response.output.response = (
                                response.output.response[:1997] + "..."
                            )
                            self.logger.info(
                                "Message was too long, truncated to 2000 characters."
                            )

                        msg = await message.channel.send(response.output.response)

                    else:
                        msg = await message.channel.send(command.command_response)

                command.last_used = discord.utils.utcnow()
                command.save()

                return msg


async def setup(bot):
    await bot.add_cog(Commands(bot))
