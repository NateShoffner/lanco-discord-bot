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

    @commands.command(name="techbro", description="Provide techbro advice")
    async def techbro(self, ctx: commands.Context):
        problem = await self.get_user_prompt(ctx)

        if not problem:
            await ctx.send("Please provide a problem")
            return

        techbro_response = await self.prompt_openai(
            "Provide techbro advice for the following issue and make sure to insist on how your solution/product can change the world to be a better place even if it's not true:\n"
            + problem
        )
        await ctx.send(techbro_response)

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

    @commands.command(name="boomer", description="Respond like a boomer")
    async def boomer(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        boomer_response = await self.prompt_openai(
            "Provide advice for the following issue as if you're a boomer/somebody severely out of touch with the current generation/social climate by being passive aggressive and judgemental about younger generations:\n"
            + issue
        )
        await ctx.send(boomer_response)

    @commands.command("zoomer", description="Respond like a zoomer", aliases=["genz"])
    async def zoomer(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        zoomer_response = await self.prompt_openai(
            "Provide advice for the following issue as if you're a zoomer/somebody severely out of touch with the older generations. Be very judgemental of older generations and try to throw in as much zoomer language/jargon as possible:\n"
            + issue
        )
        await ctx.send(zoomer_response)

    @commands.command("millenial", description="Respond like a millenial")
    async def millenial(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        mag_response = await self.prompt_openai(
            "Provide advice for the following issue as if you're a millenial and largely apathetic to most situations and have adapted coping mechanisms and insist on joking about otherwise depressing situations:\n"
            + issue
        )
        await ctx.send(mag_response)

    @commands.command("genx", description="Respond like a genx")
    async def genx(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        mag_response = await self.prompt_openai(
            "Provide advice for the following issue as if you're a grumpy gen x-er who insists on talking about how hard life was for them and how they were stuck between the analog and digital world. Definitely make sure to mention playing outside as a kid:\n"
            + issue
        )
        await ctx.send(mag_response)

    @commands.command("josiahsupport", description="Respond like josiah")
    async def josiahsupport(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        mag_response = await self.prompt_openai(
            "Respond to the prompt but always find a way to make it relevent to the conversation of water, seweage, water treatment, or environmental engineering:\n"
            + issue
        )
        await ctx.send(mag_response)

    @commands.command("smilesupport", description="Respond like endormi")
    async def smilesupport(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        mag_response = await self.prompt_openai(
            "Respond to the prompt but always find a way to make it relevent to the conversation of social psychology\n"
            + issue
        )
        await ctx.send(mag_response)

    @commands.command("anime", description="Respond like a anime character")
    async def anime(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        anime_response = await self.prompt_openai(
            "Respond to the following prompt as if you're in an anime. Be as dramatic and over the top as possible and try to throw in as many anime tropes as you can:\n"
            + issue
        )
        await ctx.send(anime_response)

    @commands.command("ceo", description="Respond like a ceo character")
    async def ceo(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        ceo_response = await self.prompt_openai(
            "Re-state the following message in the most buzzwordy way possible as if you're a CEO:\n"
            + issue
        )
        await ctx.send(ceo_response)

    @commands.command(name="eli5", description="Explain like I'm 5")
    async def eli5(self, ctx: commands.Context):
        question = await self.get_user_prompt(ctx)
        eli5_response = await self.prompt_openai(
            "Give me a dumbed down version of this message as if I'm 5 years old:\n"
            + question
        )

        if not eli5_response or len(eli5_response) == 0:
            await ctx.send("There's no possible way to dumb this down further")
            return

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
