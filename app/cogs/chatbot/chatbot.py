import discord
from cogs.lancocog import LancoCog
from discord.ext import commands
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import ModelMessage


class ChannelDiscussion(BaseModel):
    response: str = Field(
        ...,
        description="The response from the chatbot based on the user's input",
    )


class ChatBot(
    LancoCog, name="ChatBot", description="User-specific chatbot with agent memory"
):
    def __init__(self, bot):
        super().__init__(bot)
        self.channel_agents: dict[int, Agent] = {}
        self.channel_responses: dict[int, AgentRunResult] = {}

    def get_agent(self, channel: discord.TextChannel) -> Agent:
        PROMPT = f"Your name is {self.bot.user.name}. You are a helpful assistant chatting with users in the {channel.name} channel of the {channel.guild.name} server. Remember the context of the conversation and respond accordingly."

        if channel.id not in self.channel_agents:
            agent = Agent(
                model="openai:gpt-4o",
                system_prompt=PROMPT,
                output_type=ChannelDiscussion,
            )
            self.channel_agents[channel.id] = agent
        return self.channel_agents[channel.id]

    def get_last_response(self, channel: discord.TextChannel) -> AgentRunResult:
        return self.channel_responses.get(channel.id, None)

    @commands.Cog.listener()
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

        if self.bot.user.mentioned_in(message):
            # strip bot mention from message content
            content = message.clean_content.replace(
                f"@{self.bot.user.name}", ""
            ).strip()
            if not content:
                return

            text = message.content.strip()

            agent = self.get_agent(message.channel)
            last_response = self.get_last_response(message.channel)
            history = []
            if last_response:
                history = last_response.new_messages()

            await message.channel.typing()
            response = await agent.run(text, history=history)

            # Store the response for future reference
            self.channel_responses[message.channel.id] = response

            await message.channel.send(response.output.response)


async def setup(bot):
    await bot.add_cog(ChatBot(bot))
