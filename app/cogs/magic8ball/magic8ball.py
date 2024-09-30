import random

from cogs.lancocog import LancoCog
from discord.ext import commands


class Magic8Ball(LancoCog, name="Magic8Ball", description="Magic 8 Ball"):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    @commands.command(name="8ball", description="Ask the magic 8 ball a question")
    async def eight_ball(self, ctx: commands.Context, *, question: str = None):
        """Ask the magic 8 ball a question"""
        responses = [
            "It is certain.",
            "It is decidedly so.",
            "Without a doubt.",
            "Yes - definitely.",
            "You may rely on it.",
            "As I see it, yes.",
            "Most likely.",
            "Outlook good.",
            "Yes.",
            "Signs point to yes.",
            "Reply hazy, try again.",
            "Ask again later.",
            "Better not tell you now.",
            "Cannot predict now.",
            "Concentrate and ask again.",
            "Don't count on it.",
            "My reply is no.",
            "My sources say no.",
            "Outlook not so good.",
            "Very doubtful.",
        ]

        response = random.choice(responses)
        response_msg = ""
        if question:
            response_msg = f"Question: {question}\n"
        response_msg += f"Answer: {response}"
        await ctx.send(response_msg)


async def setup(bot):
    await bot.add_cog(Magic8Ball(bot))
