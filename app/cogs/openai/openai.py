import base64
import os

import openai
from cogs.lancocog import LancoCog
from discord.ext import commands


class OpenAI(
    LancoCog,
    name="OpenAI",
    description="OpenAI commands",
):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.client = openai.Client(api_key=os.getenv("OPENAI_API_KEY"))
        self.cache_dir = os.path.join(self.get_cog_data_directory(), "Cache")

    def encode_image(self, image_path: str):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    # identify command
    @commands.command(name="explain", description="Explain something")
    async def explain(self, ctx: commands.Context):
        is_file = False
        # Check if there is an attachment
        if ctx.message.attachments:
            is_file = True

        if is_file:
            # TODO - handle multiple attachments
            results = await self.download_attachments(ctx.message, self.cache_dir)
            filename = results[0].filename
            encoded = self.encode_image(filename)

            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that responds in Markdown.",
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe this image"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{encoded}"
                                },
                            },
                        ],
                    },
                ],
                temperature=0.0,
            )

            await ctx.send(response.choices[0].message.content)


async def setup(bot):
    await bot.add_cog(OpenAI(bot))
