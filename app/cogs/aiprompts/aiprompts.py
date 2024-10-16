import os
from cmd import PROMPT

import discord
from cogs.lancocog import LancoCog
from discord import TextChannel, app_commands
from discord.ext import commands
from openai import AsyncOpenAI
from reactionmenu import ReactionButton, ReactionMenu
from utils.channel_lock import command_channel_lock
from utils.command_utils import is_bot_owner_or_admin
from utils.tracked_message import track_message_ids

from .models import AIPromptConfig


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
        self.conversations = (
            {}
        )  # key: conversation list of prompts and responses (tuple)

    async def get_user_prompt(self, ctx: commands.Context) -> str:
        if ctx.message.reference:
            ref_message = await ctx.fetch_message(ctx.message.reference.message_id)
            return ref_message.content

        split = ctx.message.content.split(" ", 1)
        if len(split) > 1:
            return ctx.message.content.split(" ", 1)[1]

        return None

    def get_conversation_key(self, user_message: discord.Message, ai_name: str):
        return f"{user_message.guild.id}-{user_message.channel.id}-{user_message.author.id}-{ai_name}"

    async def prompt_openai(
        self,
        ai_name: str,
        user_message: discord.Message,
        user_prompt: str,
        max_tokens: int = 250,
        temperature: int = 0,
        n: int = 1,
    ) -> str:
        messages = []

        if ai_name and user_message:
            conversation_key = self.get_conversation_key(user_message, ai_name)

            if not conversation_key in self.conversations:
                self.conversations[conversation_key] = []
            previous_questions_and_answers = self.conversations[conversation_key]

            # add the previous questions and answers
            for question, answer in previous_questions_and_answers[
                -self.MAX_CONTEXT_QUESTIONS :
            ]:
                messages.append({"role": "user", "content": question})
                messages.append({"role": "assistant", "content": answer})
            # add the new question
        messages.append({"role": "user", "content": user_prompt})

        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=1,
        )

        content = response.choices[0].message.content
        return content.encode("utf-8").decode()

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
            ai_response = await self.prompt_openai(
                prompt_config.name, message, formatted_message
            )

            return await message.channel.send(ai_response)

    @commands.command(name="ai", description="Generic AI prompt")
    async def ai(self, ctx: commands.Context):
        prompt = await self.get_user_prompt(ctx)
        ai_response = await self.prompt_openai("ai", ctx.message, prompt)
        await ctx.send(ai_response)

    @commands.command(name="eli5", description="Explain like I'm 5")
    async def eli5(self, ctx: commands.Context):
        question = await self.get_user_prompt(ctx)
        eli5_response = await self.prompt_openai(
            "eli5",
            ctx.message,
            "Give me a dumbed down version of this message as if I'm 5 years old:\n"
            + question,
        )

        if not eli5_response or len(eli5_response) == 0:
            await ctx.send("There's no possible way to dumb this down further")
            return

        await ctx.send("Here's the dumbed down version:\n\n" + eli5_response)

    @commands.command(
        name="topic", description="Will say what the current channel is talking about"
    )
    @command_channel_lock()
    async def topic(self, ctx: commands.Context):
        channel = ctx.channel
        topics = await self.get_current_channel_topics(channel)

        if not topics or len(topics) == 0:
            await ctx.send("No topics found")
            return

        top_topics = topics[:3]
        await ctx.send(f"Currently being discussed: {', '.join(top_topics)}")

    @commands.command(name="vibecheck", description="Check the vibe")
    @command_channel_lock()
    async def vibecheck(self, ctx: commands.Context):
        messages = await self.get_current_channel_convo(ctx.channel)

        if len(messages) == 0:
            await ctx.send("No messages found")
            return

        vibe_response = await self.prompt_openai(
            "vibecheck",
            ctx.message,
            "Check the vibe of the following messages and try to keep it under 75 words:\n"
            + "\n".join([m.content for m in messages]),
        )

        await ctx.send(vibe_response)

    @commands.command(name="chime", description="Chime in on the current topic")
    @command_channel_lock()
    async def chime(self, ctx: commands.Context):
        channel = ctx.channel
        topics = await self.get_current_channel_topics(channel, history_limit=5)

        if not topics or len(topics) == 0:
            await ctx.send("No topics found")
            return

        top_topics = topics[:3]

        self.logger.info(f"Topics: {top_topics}")

        response = await self.prompt_openai(
            "Chime in on or more of the following topics: "
            + ", ".join(top_topics)
            + "\nTry to keep it short and concise, ideally less than 75 words"
        )

        await ctx.send(response)

    async def get_current_channel_convo(
        self, channel: TextChannel, history_limit: int = 25
    ) -> list[str]:
        messages = []
        messages = [
            msg
            async for msg in channel.history(limit=history_limit, oldest_first=False)
        ]
        messages = [
            m
            for m in messages
            if not m.author.bot
            and m.content.strip() != ""
            and not m.content.startswith(".")
            and not m.content.startswith("!")
            and not m.embeds
            and not m.attachments
            and not m.author.bot
        ]
        messages.reverse()
        return messages

    async def get_current_channel_topics(
        self, channel: TextChannel, history_limit: int = 25
    ) -> list[str]:
        messages = await self.get_current_channel_convo(channel, history_limit)

        if len(messages) == 0:
            self.logger.info("No messages found")
            return []

        response = await self.prompt_openai(
            None,
            None,
            "Extract primary topics from the following messages and list them separated by commas, ordered by relvance:\n"
            + "\n".join([m.content for m in messages]),
        )

        topics = []

        is_newline_separated = response.count("\n") > 2

        if is_newline_separated:
            for line in response.split("\n"):
                line = line.lstrip("1234567890. ")
                topics.append(line)
        else:
            for line in response.split(","):
                line = line.lstrip("1234567890. ")
                topics.append(line)

        return topics


async def setup(bot):
    await bot.add_cog(OpenAIPrompts(bot))
