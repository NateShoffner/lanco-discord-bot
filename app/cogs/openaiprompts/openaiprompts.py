import os
from discord import TextChannel
import openai
from discord.ext import commands
from cogs.lancocog import LancoCog


class OpenAIPrompts(
    LancoCog,
    name="OpenAIPrompts",
    description="OpenAI prompts for various situations",
):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        openai.api_key = os.getenv("OPENAI_API_KEY")

    async def get_user_prompt(self, ctx: commands.Context) -> str:
        if ctx.message.reference:
            ref_message = await ctx.fetch_message(ctx.message.reference.message_id)
            return ref_message.content

        split = ctx.message.content.split(" ", 1)
        if len(split) > 1:
            return ctx.message.content.split(" ", 1)[1]

        return None

    async def prompt_openai(
        self, prompt: str, max_tokens: int = 150, temperature: int = 0, n: int = 1
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

    @commands.command(name="therapy", description="Provide therapy")
    async def therapy(self, ctx: commands.Context):
        problem = await self.get_user_prompt(ctx)

        if not problem:
            await ctx.send("Please provide a problem")
            return

        therapy_response = await self.prompt_openai(
            "Provide a therapist-like resonse to this situation :\n" + problem
        )
        await ctx.send(therapy_response)

    @commands.command(
        name="techsupport", description="Provide tech support", aliases=["itbtw"]
    )
    async def techsupport(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        tech_response = await self.prompt_openai(
            "Provide tech support for the following issue:\n" + issue
        )
        await ctx.send(tech_response)

    @commands.command(name="ai", description="General AI prompt")
    async def ai(self, ctx: commands.Context):
        prompt = await self.get_user_prompt(ctx)
        ai_response = await self.prompt_openai(prompt)  
        await ctx.send(ai_response)

    @commands.command(name="magsupport", description="Provide tech support")
    async def magsupport(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        mag_response = await self.prompt_openai(
            "Provide tech support for the following issue but in a very passive aggressive and unhelpful tone:\n"
            + issue
        )
        await ctx.send(
            "Hello, Magnific Osprey here providing tech support:\n\n" + mag_response
        )

    @commands.command(name="eli5", description="Explain like I'm 5")
    async def eli5(self, ctx: commands.Context):
        question = await self.get_user_prompt(ctx)
        eli5_response = await self.prompt_openai(
            "Give me a dumbed down version of this message as if I'm 5 years old:\n"
            + question
        )
        await ctx.send("Here's the dumbed down version:\n\n" + eli5_response)

    @commands.command(
        name="topic", description="Will say what the current channel is talking about"
    )
    async def topic(self, ctx: commands.Context):
        channel = ctx.channel
        topics = await self.get_current_channel_topics(channel)

        if not topics or len(topics) == 0:
            await ctx.send("No topics found")
            return

        top_topics = topics[:3]
        await ctx.send(f"Topics found: {', '.join(top_topics)}")

    async def get_current_channel_topics(self, channel: TextChannel) -> list[str]:
        messages = [msg async for msg in channel.history(limit=50, oldest_first=False)]
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
            "Extract primary topics from the following messages and list them separated by commas:\n"
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
    await bot.add_cog(OpenAIPrompts(bot))
