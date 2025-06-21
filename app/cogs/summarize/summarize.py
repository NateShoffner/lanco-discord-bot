"""
Summarize Cog

Description:
Provides summarization capabilities for Discord channels, allowing users to get a brief overview of the topics being discussed in a channel.
"""

import discord
from cogs.lancocog import LancoCog
from discord import TextChannel, app_commands
from discord.ext import commands
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from reactionmenu import ReactionButton, ReactionMenu
from utils.channel_lock import command_channel_lock
from utils.command_utils import is_bot_owner_or_admin
from utils.message_utils import get_user_messages
from utils.tracked_message import track_message_ids


class ChannelDiscussion(BaseModel):
    topics: list[str] = Field(
        ..., description="List of topics being discussed in the channel"
    )


class Summarize(
    LancoCog,
    name="summarize",
    description="Summarize Cog",
):
    def __init__(self, bot):
        super().__init__(bot)
        self.agent = Agent(
            model="openai:gpt-4o",
            system_prompt="You are a helpful assistant that analyzes channel discussions and determines trending topics.",
            output_type=ChannelDiscussion,
        )

    @commands.command(
        name="topic", description="Will say what the current channel is talking about"
    )
    @command_channel_lock()
    @track_message_ids()
    async def topic(self, ctx: commands.Context):
        await ctx.channel.typing()
        messages = await get_user_messages(ctx.channel, limit=50, oldest_first=True)

        print(messages)

        if not messages or len(messages) == 0:
            self.logger.info("No messages found")
            return None

        result = await self.agent.run(
            [
                "Analyze the following messages and extract the primary topics being discussed. "
                "Return a list of topics ordered by relevance.",
            ]
            + [m.content for m in messages]
        )

        if not result or not result.output or len(result.output.topics) == 0:
            self.logger.info("No topics found")
            return await ctx.send("No topics found in the channel.")

        max_topics = 3

        top_topics = result.output.topics[:max_topics]
        markdown_list = "\n".join([f"* {topic}" for topic in top_topics])
        msg = await ctx.send(f"Currently being discussed: \n{markdown_list}")
        return msg


async def setup(bot):
    await bot.add_cog(Summarize(bot))
