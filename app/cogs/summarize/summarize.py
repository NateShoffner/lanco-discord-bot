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
    eli5_explanation: str = Field(
        ...,
        description="A simple explanation of the current channel's vibe, suitable for a 5-year-old",
    )
    opinion: str = Field(
        ...,
        description="Provide some insight or opinion on the current discussion in the channel. Being critical is okay, but be respectful, constructive, and concise.",
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
        embed = discord.Embed(
            title="Analyzing Channel Topics",
            description="Please wait while we analyze the channel for trending topics.",
        )

        await ctx.channel.typing()
        msg = await ctx.send(embed=embed)

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
        embed = discord.Embed(
            title="Trending Topics",
            description=f"The current trending topics in this channel are:\n{markdown_list}",
        )

        await msg.edit(embed=embed)
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

    @commands.command(
        name="eli5",
        description="Explain Like I'm 5 - provides a simple explanation of the current channel's vibe",
    )
    @command_channel_lock()
    @track_message_ids()
    async def eli5(self, ctx: commands.Context):
        await ctx.channel.typing()

        # TODO - if a message is not referenced, get the summary of the channel and then use that as the prompt
        prompt = await self.get_user_prompt(ctx)

        if not prompt:
            return await ctx.send("Please provide a prompt for the ELI5 explanation.")

        result = await self.agent.run(prompt)

        if not result or not result.output or not result.output.eli5_explanation:
            self.logger.info("No ELI5 explanation found")
            return

        eli5_explanation = result.output.eli5_explanation
        msg = await ctx.send(eli5_explanation)
        return msg

    @commands.command(
        name="chime",
        description="Chime in on the current conversation with an opinion or insight",
    )
    @command_channel_lock()
    @track_message_ids()
    async def chime(self, ctx: commands.Context):
        await ctx.channel.typing()
        messages = await get_user_messages(ctx.channel, limit=25)

        if not messages or len(messages) == 0:
            self.logger.info("No messages found")
            return None

        result = await self.agent.run([m.content for m in messages])

        if not result or not result.output or not result.output.opinion:
            self.logger.info("No opinion found")
            return await ctx.send("No opinion could be determined for the channel.")

        opinion = result.output.opinion
        msg = await ctx.send(opinion)
        return msg

    async def get_user_prompt(self, ctx: commands.Context) -> str:
        if ctx.message.reference:
            ref_message = await ctx.fetch_message(ctx.message.reference.message_id)
            return ref_message.content

        split = ctx.message.content.split(" ", 1)
        if len(split) > 1:
            return ctx.message.content.split(" ", 1)[1]

        return None


async def setup(bot):
    await bot.add_cog(Summarize(bot))
