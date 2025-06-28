import os

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from reactionmenu import ReactionButton, ReactionMenu
from utils.command_utils import is_bot_owner_or_admin
from utils.tracked_message import track_message_ids

from .models import AIPromptConfig


class CustomBotConversation(BaseModel):
    response: str = Field(
        ...,
        description="The response from the chatbot based on the user's input",
    )


class PromptModal(discord.ui.Modal, title="Prompt Info"):
    name_input = discord.ui.TextInput(
        label="Enter a command name:",
        style=discord.TextStyle.short,
        required=True,
    )

    prompt_input = discord.ui.TextInput(
        label="Enter a prompt:",
        style=discord.TextStyle.long,
        required=True,
        placeholder="Enter a prompt with %prompt% tokens",
    )

    def __init__(self, config: AIPromptConfig = None):
        super().__init__(timeout=None)
        self.config = config
        if config:
            self.prompt_input.default = config.prompt

    async def on_submit(self, interaction: discord.Interaction) -> None:
        edit = self.config is not None
        name = self.name_input.value
        if not edit:
            config, created = AIPromptConfig.get_or_create(
                guild_id=interaction.guild.id,
                name=name,
                prompt=self.prompt_input.value,
            )
            self.config = config

        self.config.prompt = self.prompt_input.value
        self.config.save()

        await interaction.response.send_message(
            f"AI Prompt added: {name}" if not edit else f"AI Prompt updated: {name}"
        )


class OpenAIPrompts(
    LancoCog,
    name="OpenAIPrompts",
    description="OpenAI prompts for various situations",
):
    MAX_CONTEXT_QUESTIONS = 25

    g = app_commands.Group(name="aiprompt", description="AI prompt commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.bot.database.create_tables([AIPromptConfig])
        self.custom_agents: dict[int, Agent] = {}  # AI ID -> Agent

    def get_agent(self, AIpromptConfig: AIPromptConfig) -> Agent:
        ai_id = AIpromptConfig.id
        if ai_id not in self.custom_agents:
            agent = Agent(
                model="openai:gpt-4o",
                system_prompt="You are a helpful assistant that responds to user queries.",
                output_type=CustomBotConversation,
            )
            self.custom_agents[ai_id] = agent
        return self.custom_agents[ai_id]

    async def get_user_prompt(self, ctx: commands.Context) -> str:
        if ctx.message.reference:
            ref_message = await ctx.fetch_message(ctx.message.reference.message_id)
            return ref_message.content

        split = ctx.message.content.split(" ", 1)
        if len(split) > 1:
            return ctx.message.content.split(" ", 1)[1]

        return None

    @g.command(name="add", description="Add an AI prompt")
    @is_bot_owner_or_admin()
    async def add_prompt(self, interaction: discord.Interaction):
        modal = PromptModal()
        await interaction.response.send_modal(modal)

    @g.command(name="edit", description="Edit an AI prompt")
    @is_bot_owner_or_admin()
    async def add_prompt(self, interaction: discord.Interaction, name: str):
        prompt = AIPromptConfig.get_or_none(guild_id=interaction.guild.id, name=name)
        modal = PromptModal(prompt)
        await interaction.response.send_modal(modal)

    @g.command(name="list", description="List all AI prompts")
    async def list_prompts(self, interaction: discord.Interaction):
        prompts = AIPromptConfig.select().where(
            AIPromptConfig.guild_id == interaction.guild.id
        )

        if not prompts:
            await interaction.response.send_message("No prompts found", ephemeral=True)
            return

        menu = ReactionMenu(interaction, menu_type=ReactionMenu.TypeEmbed)

        PROMPTS_PER_PAGE = 5
        for i in range(0, len(prompts), PROMPTS_PER_PAGE):
            page = prompts[i : i + PROMPTS_PER_PAGE]
            embed = discord.Embed(title="AI prompts for this server")
            embed.description = "\n".join([f"**{p.name}**: {p.prompt}\n" for p in page])
            menu.add_page(embed)

        if len(prompts) > PROMPTS_PER_PAGE:
            menu.add_button(ReactionButton.go_to_first_page())
            menu.add_button(ReactionButton.back())
            menu.add_button(ReactionButton.next())
            menu.add_button(ReactionButton.go_to_page())
            menu.add_button(ReactionButton.go_to_last_page())

        menu.add_button(ReactionButton.end_session())

        await menu.start()

    @g.command(name="remove", description="Remove an AI prompt")
    @is_bot_owner_or_admin()
    async def remove_prompt(self, interaction: discord.Interaction, name: str):
        prompt = AIPromptConfig.get_or_none(guild_id=interaction.guild.id, name=name)
        if not prompt:
            await interaction.response.send_message("Prompt not found", ephemeral=True)
            return

        prompt.delete_instance()
        await interaction.response.send_message("Prompt removed", ephemeral=True)

    @commands.Cog.listener()
    @track_message_ids()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if isinstance(message.channel, discord.DMChannel):
            return

        if message.content.startswith(self.bot.command_prefix):
            command_name, *args = message.content.split(" ")
            command_name = command_name[len(self.bot.command_prefix) :]

            prompt_config = AIPromptConfig.get_or_none(
                guild_id=message.guild.id, name=command_name.lower()
            )

            if not prompt_config:
                return

            self.logger.info(f"AI Prompt command: {command_name}")

            ctx = await self.bot.get_context(message)
            user_prompt = await self.get_user_prompt(ctx)

            formatted_message = prompt_config.prompt.replace("%prompt%", user_prompt)

            agent = self.get_agent(prompt_config)

            if not agent:
                await message.channel.send("No AI agent configured for this prompt.")
                return

            await message.channel.typing()

            self.logger.info(f"Running AI agent for prompt: {prompt_config.name}")
            self.logger.info(f"Formatted message: {formatted_message}")

            # TODO pass in message history
            response = await agent.run(formatted_message)

            await message.channel.send(response.output.response)

    @commands.command(name="ai", description="Generic AI prompt")
    async def ai(self, ctx: commands.Context):
        prompt = await self.get_user_prompt(ctx)
        ai_response = await self.prompt_openai("ai", ctx.message, prompt)
        await ctx.send(ai_response)


async def setup(bot):
    await bot.add_cog(OpenAIPrompts(bot))
