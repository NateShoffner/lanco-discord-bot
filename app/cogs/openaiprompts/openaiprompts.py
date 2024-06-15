import os

import discord
from cogs.lancocog import LancoCog
from discord import TextChannel
from discord.ext import commands
from openai import AsyncOpenAI


class OpenAIPrompts(
    LancoCog,
    name="OpenAIPrompts",
    description="OpenAI prompts for various situations",
):
    MAX_CONTEXT_QUESTIONS = 25

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.conversations = (
            {}
        )  # key: conversation list of prompts and responses (tuple)

    async def get_user_prompt(self, ctx: commands.Context) -> str:
        if ctx.message.reference:
            ref_message = await ctx.fetch_message(ctx.message.reference.message_id)
            return ref_message.content

        split = ctx.message.content.split(" ", 1)
        if len(split) > 1:
            return ctx.message.content.split(" ", 1)[1]

        return None

    def get_conversation_key(self, user_message: discord.Message, ai_name: str):
        return f"{user_message.guild.id}-{user_message.channel.id}-{user_message.author.id}-{ai_name}"

    async def prompt_openai(
        self,
        ai_name: str,
        user_message: discord.Message,
        user_prompt: str,
        max_tokens: int = 250,
        temperature: int = 0,
        n: int = 1,
    ) -> str:

        messages = []

        if ai_name and user_message:
            conversation_key = self.get_conversation_key(user_message, ai_name)

            if not conversation_key in self.conversations:
                self.conversations[conversation_key] = []
            previous_questions_and_answers = self.conversations[conversation_key]

            # add the previous questions and answers
            for question, answer in previous_questions_and_answers[
                -self.MAX_CONTEXT_QUESTIONS :
            ]:
                messages.append({"role": "user", "content": question})
                messages.append({"role": "assistant", "content": answer})
            # add the new question
        messages.append({"role": "user", "content": user_prompt})

        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=1,
        )

        content = response.choices[0].message.content
        return content.encode("utf-8").decode()

    @commands.command(name="therapy", description="Provide therapy")
    async def therapy(self, ctx: commands.Context):
        problem = await self.get_user_prompt(ctx)

        if not problem:
            await ctx.send("Please provide a problem")
            return

        therapy_response = await self.prompt_openai(
            "therapy",
            ctx.message,
            "Provide a therapist-like resonse to this situation :\n" + problem,
        )
        await ctx.send(therapy_response)

    @commands.command(name="techbro", description="Provide techbro advice")
    async def techbro(self, ctx: commands.Context):
        problem = await self.get_user_prompt(ctx)

        if not problem:
            await ctx.send("Please provide a problem")
            return

        techbro_response = await self.prompt_openai(
            "techbro",
            ctx.message,
            "Provide techbro advice for the following issue and make sure to insist on how your solution/product can change the world to be a better place even if it's not true:\n"
            + problem,
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

        if not prompt:
            await ctx.send("Please provide a prompt")
            return

        ai_response = await self.prompt_openai(
            "ai", ctx.message, prompt, max_tokens=800
        )

        if not ai_response or len(ai_response) == 0:
            await ctx.send("idk lmao")
            return

        # split the response into multiple messages if it's too long
        if len(ai_response) > 2000:
            for i in range(0, len(ai_response), 2000):
                await ctx.send(ai_response[i : i + 2000])

        await ctx.send(ai_response)

    @commands.command(name="magsupport", description="Provide tech support")
    async def magsupport(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        mag_response = await self.prompt_openai(
            "magsupport",
            ctx.message,
            "Provide tech support for the following issue but in a very passive aggressive and unhelpful tone:\n"
            + issue,
        )
        await ctx.send(
            "Hello, Magnific Osprey here providing tech support:\n\n" + mag_response
        )

    @commands.command(name="amishtechsupport", description="Provide Amish tech support")
    async def amishtechsupport(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        amish_response = await self.prompt_openai(
            "amishtechsupport",
            ctx.message,
            "Provide tech support for the following issue but from the perspective of an Amish person who can only diagnose the issue from the familiarity of working on a farm and provide solutions with verbiage relating to farm life.\n"
            + issue,
        )
        await ctx.send(
            "Hello, Asus Miller here providing tech support:\n\n" + amish_response
        )

    @commands.command(name="financialguru", description="Provide financial advice")
    async def financialguru(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        finance_response = await self.prompt_openai(
            "financialguru",
            ctx.message,
            "Provide the worst possible financial advice for the following situation but phrase it as if it's actually good advice:\n"
            + issue,
        )
        await ctx.send("Ronald Dump, financial guru here:\n\n" + finance_response)

    @commands.command(name="doctor", description="Provide medical advice")
    async def doctor(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        medical_response = await self.prompt_openai(
            "doctor",
            ctx.message,
            "Provide the worst possible medical advice for the following situation but phrase it as if it's actually good advice. Make sure to talk about home remedies that don't actually work and pseudo-science:\n"
            + issue,
        )
        await ctx.send("Dr. Harry Richard here:\n\n" + medical_response)

    @commands.command(name="lawyer", description="Provide legal advice")
    async def lawyer(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        legal_response = await self.prompt_openai(
            "lawyer",
            ctx.message,
            "Provide the worst possible legal advice for the following situation but phrase it as if it's actually good advice:\n"
            + issue,
        )
        await ctx.send("Rudey Juliani here:\n\n" + legal_response)

    @commands.command(name="boomer", description="Respond like a boomer")
    async def boomer(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        boomer_response = await self.prompt_openai(
            "boomer",
            ctx.message,
            "Provide advice for the following issue as if you're a boomer/somebody severely out of touch with the current generation/social climate by being passive aggressive and judgemental about younger generations:\n"
            + issue,
        )
        await ctx.send(boomer_response)

    @commands.command("zoomer", description="Respond like a zoomer", aliases=["genz"])
    async def zoomer(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        zoomer_response = await self.prompt_openai(
            "zoomer",
            ctx.message,
            "Provide advice for the following issue as if you're a zoomer/somebody severely out of touch with the older generations. Be very judgemental of older generations and try to throw in as much zoomer language/jargon as possible:\n"
            + issue,
        )
        await ctx.send(zoomer_response)

    @commands.command("millenial", description="Respond like a millenial")
    async def millenial(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        mag_response = await self.prompt_openai(
            "millenial",
            ctx.message,
            "Provide advice for the following issue as if you're a millenial and largely apathetic to most situations and have adapted coping mechanisms and insist on joking about otherwise depressing situations:\n"
            + issue,
        )
        await ctx.send(mag_response)

    @commands.command("genx", description="Respond like a genx")
    async def genx(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        mag_response = await self.prompt_openai(
            "genx",
            ctx.message,
            "Provide advice for the following issue as if you're a grumpy gen x-er who insists on talking about how hard life was for them and how they were stuck between the analog and digital world. Definitely make sure to mention playing outside as a kid:\n"
            + issue,
        )
        await ctx.send(mag_response)

    @commands.command("josiahsupport", description="Respond like josiah")
    async def josiahsupport(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        mag_response = await self.prompt_openai(
            "josiahsupport",
            ctx.message,
            "Respond to the prompt but always find a way to make it relevent to the conversation of water, seweage, water treatment, or environmental engineering:\n"
            + issue,
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

    @commands.command("weeb", description="Respond like a anime character")
    async def weeb(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        anime_response = await self.prompt_openai(
            "weeb",
            ctx.message,
            "Respond to the following prompt as if you're in an anime. Be as dramatic and over the top as possible and try to throw in as many anime tropes as you can:\n"
            + issue,
        )
        await ctx.send(anime_response)

    @commands.command("ceo", description="Respond like a ceo character")
    async def ceo(self, ctx: commands.Context):
        issue = await self.get_user_prompt(ctx)
        ceo_response = await self.prompt_openai(
            "ceo",
            ctx.message,
            "Re-state the following message in the most buzzwordy way possible as if you're a CEO:\n"
            + issue,
        )
        await ctx.send(ceo_response)

    @commands.command(name="eli5", description="Explain like I'm 5")
    async def eli5(self, ctx: commands.Context):
        question = await self.get_user_prompt(ctx)
        eli5_response = await self.prompt_openai(
            "eli5",
            ctx.message,
            "Give me a dumbed down version of this message as if I'm 5 years old:\n"
            + question,
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
        await ctx.send(f"Currently being discussed: {', '.join(top_topics)}")

    # vibe check command
    @commands.command(name="vibecheck", description="Check the vibe")
    async def vibecheck(self, ctx: commands.Context):
        messages = await self.get_current_channel_convo(ctx.channel)

        if len(messages) == 0:
            await ctx.send("No messages found")
            return

        vibe_response = await self.prompt_openai(
            "vibecheck",
            ctx.message,
            "Check the vibe of the following messages and try to keep it under 75 words:\n"
            + "\n".join([m.content for m in messages]),
        )

        await ctx.send(vibe_response)

    @commands.command(name="chime", description="Chime in on the current topic")
    async def chime(self, ctx: commands.Context):
        channel = ctx.channel
        topics = await self.get_current_channel_topics(channel, history_limit=5)

        if not topics or len(topics) == 0:
            await ctx.send("No topics found")
            return

        top_topics = topics[:3]

        self.logger.info(f"Topics: {top_topics}")

        response = await self.prompt_openai(
            "Chime in on or more of the following topics: "
            + ", ".join(top_topics)
            + "\nTry to keep it short and concise, ideally less than 75 words"
        )

        await ctx.send(response)

    async def get_current_channel_convo(
        self, channel: TextChannel, history_limit: int = 25
    ) -> list[str]:
        messages = []
        messages = [
            msg
            async for msg in channel.history(limit=history_limit, oldest_first=False)
        ]
        messages = [
            m
            for m in messages
            if not m.author.bot
            and m.content.strip() != ""
            and not m.content.startswith(".")
            and not m.content.startswith("!")
            and not m.embeds
            and not m.attachments
            and not m.author.bot
        ]
        messages.reverse()
        return messages

    async def get_current_channel_topics(
        self, channel: TextChannel, history_limit: int = 25
    ) -> list[str]:
        messages = await self.get_current_channel_convo(channel, history_limit)

        if len(messages) == 0:
            self.logger.info("No messages found")
            return []

        response = await self.prompt_openai(
            None,
            None,
            "Extract primary topics from the following messages and list them separated by commas, ordered by relvance:\n"
            + "\n".join([m.content for m in messages]),
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
