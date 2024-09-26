import os
import uuid

import aiohttp
import cv2
import numpy as np
from cogs.lancocog import LancoCog
from discord.ext import commands
from tensorflow.keras.applications.vgg16 import (
    VGG16,
    decode_predictions,
    preprocess_input,
)
from tensorflow.keras.preprocessing import image


class HotDog(LancoCog, name="HotDog", description="Profile Glizzies"):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.cache_dir = os.path.join(self.get_cog_data_directory(), "Cache")
        self.model = VGG16(weights="imagenet")

    @commands.command(name="hotdog", description="Is this a hotdog?")
    async def hotdog(self, ctx: commands.Context):
        result = await self.process_ai_command(ctx, "hotdog")
        if result:
            await ctx.send("That's a hotdog")
        else:
            await ctx.send("That's a **notdog**")

    async def process_ai_command(self, ctx: commands.Context, keyword: str):
        if not ctx.message.reference:
            await ctx.send("Please reply to a message with an image")

        message = await ctx.fetch_message(ctx.message.reference.message_id)

        url = None
        if message.attachments:
            self.logger.info("Attachment found in message")
            attachment = message.attachments[0]
            url = attachment.url
            ext = url.split(".")[-1].split("?")[0]
        elif message.embeds:
            self.logger.info("Embed found in message")
            embed = message.embeds[0]

            if embed.image:
                url = embed.image.proxy_url
                ext = url.split(".")[-1].split("?")[0]
            if embed.video:
                proxy_url = embed.video.proxy_url

                self.logger.info(f"Proxy URL: {proxy_url}")

                if "tenor.com" in proxy_url:
                    # tenor seems to ignore the extension but instead uses the URL path to determine the file type

                    # gif
                    # https://media.tenor.com/jv1uzXK_ELwAAAAC/fullmetal-alchemist.gif
                    # mp4
                    # https://media.tenor.com/jv1uzXK_ELwAAAPo/fullmetal-alchemist.gif

                    # mp4
                    # https://media.tenor.com/M0DJo6-jF7AAAAPo/anime-responsibilities.mp4
                    # gif
                    # https://media.tenor.com/M0DJo6-jF7AAAAAC/anime-responsibilities.gif

                    # hacky way to get the original url and get the original GIF
                    # Ex: https://images-ext-2.discordapp.net/external/PHVkBmSMxJdxhSl2dlVt9_VL4tiHyn0blDb9ZBNWLjQ/https/media.tenor.com/M0DJo6-jF7AAAAPo/anime-responsibilities.mp4

                    # parse the proxy url and replace the extension, subdomain, and path
                    tenor_url = proxy_url.split("/https/")[1]
                    url_split = tenor_url.split("/")
                    path = url_split[1]
                    if path.endswith("Po"):
                        path = path[:-2] + "AC"
                    new_url = f"https://c.tenor.com/{path}/tenor.gif"
                    url = new_url

                    # https://media.tenor.com/jv1uzXK_ELwAAAPo/fullmetal-alchemist.mp4
                    # https://c.tenor.com/jv1uzXK_ELwAAAAC/tenor.gif
                    # https://c.tenor.com/jv1uzXK_ELwAAAC/fullmetal-alchemist.gif

                    ext = "gif"

            self.logger.info(f"URL: {url}")
        else:
            await ctx.send("Please reply to a message with an image")
            return

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.read()
                    random_uuid = uuid.uuid4()

                    if not os.path.exists(self.cache_dir):
                        os.makedirs(self.cache_dir)

                    filename = os.path.join(self.cache_dir, f"{random_uuid}.{ext}")
                    with open(filename, "wb") as f:
                        f.write(data)

                    is_match = self.is_keyword(filename, keyword)
                    return is_match

    def is_keyword(self, image_path: str, keyword: str):
        # Load and preprocess the image
        img = image.load_img(image_path, target_size=(224, 224))
        img_array = image.img_to_array(img)
        img_array = np.expand_dims(img_array, axis=0)
        img_array = preprocess_input(img_array)

        # Make predictions
        predictions = self.model.predict(img_array)
        decoded_predictions = decode_predictions(predictions, top=3)[0]

        self.logger.info(f"Predictions: {decoded_predictions}")

        for pred in decoded_predictions:
            if keyword in pred[1]:
                return True

        return False


async def setup(bot):
    await bot.add_cog(HotDog(bot))
