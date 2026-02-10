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


class ChannelTopic(BaseModel):
    subject: str = Field(
        ...,
        description="Topic subject being discussed (≤ 10 words) but not in an overly-analytical/robotic way. Keep it human-friendly.",
    )
    msg_ref_ids: list[int] = Field(
        default_factory=list, description="1-3 message IDs from the transcript"
    )


class ChannelDiscussion(BaseModel):
    topics: list[ChannelTopic] = Field(
        default_factory=list,
        description="List of topics being discussed in the channel",
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
    description="Provides summarization capabilities for Discord channels",
):
    SYSTEM_PROMPT = """
    Summarize the Discord transcripts provided into trending topics. Skip over any off-topic or irrelevant messages.
    Requirements:
    - Each subject MUST include 1-3 msg_ref_ids that appear in the transcript line tags.
    - You must only use msg_ref_ids that appear in the transcript. Do not invent or repeat IDs. If you cannot find enough relevant IDs, use fewer.
    - Do NOT include timestamps, quotes, or extra sections.
    """

    def __init__(self, bot):
        super().__init__(bot)
        self.agent = Agent(
            model="openai:gpt-4o",
            system_prompt=self.SYSTEM_PROMPT,
            output_type=ChannelDiscussion,
        )

    class Transcript(BaseModel):
        """Transcript of messages with indexed tags."""

        lines: list[str]

        """ Lines of the transcript with indexed tags, e.g. [msg0] @User Message """
        msg_map: dict[int, discord.Message]

        class Config:
            arbitrary_types_allowed = True

    async def build_transcript(self, messages: list[discord.Message]) -> Transcript:
        """Build a transcript from messages with indexed tags."""
        lines = []
        # Build transcript with indexes because the LLM will likely hallucinate message ids
        msg_map = {}
        for idx, m in enumerate(messages):
            content = (m.content or "").strip()
            if not content:
                continue
            line = f"[msg{idx}] @{m.author.display_name}: {content}".strip()
            lines.append(line)
            msg_map[idx] = m
        return self.Transcript(lines=lines, msg_map=msg_map)

    @commands.command(
        name="topic", description="Will say what the current channel is talking about"
    )
    @command_channel_lock()
    @track_message_ids()
    async def topic(self, ctx: commands.Context):
        chan = ctx.channel

        embed = discord.Embed(
            title="Analyzing Channel Topics",
            description=f"Please wait while I analyze {chan.mention} for trending topics...",
        )

        await ctx.channel.typing()
        msg = await ctx.send(embed=embed)

        messages = await get_user_messages(chan, limit=100)

        if not messages or len(messages) == 0:
            self.logger.info("No messages found")
            embed.description = "No messages found to analyze."
            return await msg.edit(embed=embed)

        MAX_TOPICS = 3
        MAX_USERS_TO_MENTION = 3

        transcript = await self.build_transcript(messages)
        transcript_str = "\n".join(transcript.lines)

        prompt = (
            "You will receive a transcript where each message line includes [msgN] @<User> <Message>.\n"
            "When listing subjects, pick 1-3 msgN tags that best anchor each subject.\n\n"
            "TRANSCRIPT BEGIN\n"
            f"{transcript_str}\n"
            "TRANSCRIPT END\n"
        )

        try:
            result = await self.agent.run(prompt)
        except Exception as e:
            self.logger.error(f"Agent run failed: {e}")
            embed.description = "Failed to analyze topics."
            return await msg.edit(embed=embed)

        # Render: • <subject> - <@user1>, <@user2> - [jump](url), [jump](url)
        lines_out = []
        for t in result.output.topics[:MAX_TOPICS]:
            # Only keep tags that are actually in the transcript
            filtered_tags = [tag for tag in t.msg_ref_ids if tag in transcript.msg_map]
            topic_messages = [transcript.msg_map[tag] for tag in filtered_tags]

            topic_str = f"**{t.subject}**"

            # authors (limit to one reference per user)
            seen_users = set()
            unique_topic_messages = []
            for m in topic_messages:
                if m.author.id not in seen_users:
                    unique_topic_messages.append(m)
                    seen_users.add(m.author.id)
                if len(unique_topic_messages) >= MAX_USERS_TO_MENTION:
                    break

            citation_count = 1

            if unique_topic_messages:
                user_links = []
                for m in unique_topic_messages:
                    user_links.append(
                        f"{m.author.display_name} [[{citation_count}]]({m.jump_url})"
                    )
                    citation_count += 1
                topic_str += "\n\t" + ", ".join(user_links)
            lines_out.append(f"* {topic_str}")

        content = f"The current trending topics in {chan.mention} are:"

        if lines_out:
            content += "\n" + "\n".join(lines_out)

        embed.title = "Channel Topic Analysis"
        embed.description = content
        embed.color = discord.Color.blue()
        await msg.edit(content=None, embed=embed)
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
