import os

import discord
from cogs.lancocog import LancoCog
from discord.ext import commands
from openai import AsyncOpenAI
from utils.tracked_message import ignore_if_referenced_message_is_tracked


class Chatbot(
    LancoCog,
    name="Chatbot",
    description="General purpose chatbot",
):
    TEMPERATURE = 0.5
    MAX_TOKENS = 500
    FREQUENCY_PENALTY = 0
    PRESENCE_PENALTY = 0.6
    MAX_CONTEXT_QUESTIONS = 25

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.conversations = (
            {}
        )  # key: conversation list of prompts and responses (tuple)

    def get_conversation_key(self, user_message: discord.Message):
        return f"{user_message.guild.id}-{user_message.channel.id}-{user_message.author.id}"

    @commands.Cog.listener()
    @ignore_if_referenced_message_is_tracked()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.content.startswith(self.bot.command_prefix):
            return

        is_reply = False
        is_embed = False
        if message.reference:
            referenced_msg = await message.channel.fetch_message(
                message.reference.message_id
            )
            if referenced_msg.author.id == self.bot.user.id:
                is_reply = True
            if referenced_msg.embeds:
                is_embed = True

        if is_embed:
            return

        if is_reply or self.bot.user.mentioned_in(message):
            prompt = message.content.replace(f"<@!{self.bot.user.id}>", "").strip()

            await message.channel.typing()

            key = self.get_conversation_key(message)
            response = await self.get_response(key, prompt)

            if not response:
                return

            self.conversations[key].append((prompt, response))
            await message.channel.send(response, reference=message)

    async def get_response(self, conversation_key: str, user_prompt: str):
        if not conversation_key in self.conversations:
            self.conversations[conversation_key] = []
        previous_questions_and_answers = self.conversations[conversation_key]

        messages = []

        # add the previous questions and answers
        for question, answer in previous_questions_and_answers[
            -self.MAX_CONTEXT_QUESTIONS :
        ]:
            messages.append({"role": "user", "content": question})
            messages.append({"role": "assistant", "content": answer})
        # add the new question
        messages.append({"role": "user", "content": user_prompt})

        stream = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=self.TEMPERATURE,
            max_tokens=self.MAX_TOKENS,
            top_p=1,
            frequency_penalty=self.FREQUENCY_PENALTY,
            presence_penalty=self.PRESENCE_PENALTY,
        )

        content = stream.choices[0].message.content

        return content.encode("utf-8").decode()


async def setup(bot):
    await bot.add_cog(Chatbot(bot))
