"""
Summarize Cog

Description:
Provides summarization capabilities for Discord channels, allowing users to get a brief overview of the topics being discussed in a channel.
"""

import discord
from cogs.lancocog import LancoCog
from discord.ext import commands
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from utils.channel_lock import command_channel_lock
from utils.message_utils import get_user_messages
from utils.tracked_message import track_message_ids


class ChannelDiscussion(BaseModel):
    topics: list[str] = Field(
        ..., description="List of topics being discussed in the channel"
    )
    vibe_check: str = Field(
        ...,
        description="Provide a vibe check, containing just 1-4 words about the current vibe of the channel",
    )


class Summarize(
    LancoCog,
    name="Summarize",
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
        messages = await get_user_messages(ctx.channel, limit=50)

        if not messages or len(messages) == 0:
            self.logger.info("No messages found")
            return None

        result = await self.agent.run([m.content for m in messages])

        if not result or not result.output or len(result.output.topics) == 0:
            self.logger.info("No topics found")
            return await ctx.send("No topics found in the channel.")

        max_topics = 3

        top_topics = result.output.topics[:max_topics]
        markdown_list = "\n".join([f"* {topic}" for topic in top_topics])
        msg = await ctx.send(f"Currently being discussed: \n{markdown_list}")
        return msg

    @commands.command(
        name="vibecheck", description="Will provide a vibe check of the current channel"
    )
    @command_channel_lock()
    @track_message_ids()
    async def vibecheck(self, ctx: commands.Context):
        await ctx.channel.typing()
        messages = await get_user_messages(ctx.channel, limit=25)

        if not messages or len(messages) == 0:
            self.logger.info("No messages found")
            return None

        result = await self.agent.run([m.content for m in messages])

        if not result or not result.output or not result.output.vibe_check:
            self.logger.info("No vibe check found")
            return await ctx.send("Vibe check could be determined for the channel.")

        vibe_check = result.output.vibe_check
        msg = await ctx.send(f"Vibe check: {vibe_check}")
        return msg


async def setup(bot):
    await bot.add_cog(Summarize(bot))
