import os

import openai
from cogs.lancocog import LancoCog
from discord import TextChannel
from discord.ext import commands, tasks


class ADHDChannel(
    LancoCog,
    name="ADHDChannel",
    description="Updates the channel name and topic based on the current discussion",
):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        openai.api_key = os.getenv("OPENAI_API_KEY")

    async def prompt_openai(
        self, prompt: str, max_tokens: int = 250, temperature: int = 0, n: int = 1
    ) -> str:
        response = openai.Completion.create(
            engine="gpt-3.5-turbo-instruct",
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            n=n,
        )

        response = response.choices[0].text.strip()
        return response

    @commands.Cog.listener()
    async def on_ready(self):
        await super().on_ready()
        self.get_topics.change_interval(seconds=30)
        self.get_topics.start()

    @commands.command(name="adhd")
    async def adhd(self, ctx: commands.Context):
        """ADHD Channel"""
        channel = ctx.channel
        topics = await self.get_current_channel_topics(channel)

        if not topics or len(topics) == 0:
            await ctx.send("No topics found")
            return

        top_topics = topics[:3]
        await ctx.send(f"Currently being discussed: {', '.join(top_topics)}")

        new_name = ""
        for topic in top_topics:
            new_name += "".join(c for c in topic if c.isalnum() or c == " ")
            new_name += "-"
        await channel.edit(name=new_name, topic=f"Topics: {', '.join(top_topics)}")

    @tasks.loop(seconds=10)
    async def get_topics(self):
        self.logger.info("Checking for topics")

        channel = self.bot.get_channel(1229511339966333068)
        topics = await self.get_current_channel_topics(channel)

        if not topics or len(topics) == 0:
            await channel.send("No topics found")
            return

        top_topics = topics[:3]
        # await channel.send(f"Topics found: {', '.join(top_topics)}")

        # new_name = self.get_new_channel_name(top_topics)

    #        await channel.edit(name=new_name)

    def get_new_channel_name(self, topics: list[str]) -> str:
        new_name = "".join(c for c in topics[0] if c.isalnum() or c == " ").replace(
            " ", "-"
        )

        return new_name

    async def get_current_channel_topics(self, channel: TextChannel) -> list[str]:
        messages = [msg async for msg in channel.history(limit=25, oldest_first=False)]
        messages = [
            m
            for m in messages
            if not m.author.bot
            and m.content.strip() != ""
            and not m.content.startswith(".")
        ]
        messages.reverse()

        for m in messages:
            self.logger.info(f"{m.content}")

        if not messages or len(messages) == 0:
            self.logger.info("No messages found")
            return []

        response = await self.prompt_openai(
            "Extract primary topics from the following messages and list them separated by commas, ordered by relvance:\n"
            + "\n".join([m.content for m in messages])
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
    await bot.add_cog(ADHDChannel(bot))
