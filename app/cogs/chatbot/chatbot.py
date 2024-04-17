import os

import discord
import openai
from cogs.lancocog import LancoCog
from discord.ext import commands


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
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.conversations = (
            {}
        )  # key: conversation list of prompts and responses (tuple)

    def get_conversation_key(self, user_message: discord.Message):
        return f"{user_message.guild.id}-{user_message.channel.id}-{user_message.author.id}"

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        is_reply = False
        if message.reference:
            referenced_msg = await message.channel.fetch_message(
                message.reference.message_id
            )
            if (
                referenced_msg.author.id == self.bot.user.id
                and not referenced_msg.content.startswith(".")
            ):
                is_reply = True

        if is_reply or self.bot.user.mentioned_in(message):
            prompt = message.content.replace(f"<@!{self.bot.user.id}>", "").strip()

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

        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=self.TEMPERATURE,
            max_tokens=self.MAX_TOKENS,
            top_p=1,
            frequency_penalty=self.FREQUENCY_PENALTY,
            presence_penalty=self.PRESENCE_PENALTY,
        )

        return completion.choices[0].message.content


async def setup(bot):
    await bot.add_cog(Chatbot(bot))
