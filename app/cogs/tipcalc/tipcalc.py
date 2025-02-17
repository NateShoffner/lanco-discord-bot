import base64
import json
import math
import os

import openai
from cogs.lancocog import LancoCog
from discord import Embed, Message
from discord.ext import commands
from utils.file_downloader import FileDownloader


class TipSuggestion:
    def __init__(self, bill_amount: float, tip_percentage: float):
        self.bill_amount = bill_amount
        self.tip_percentage = tip_percentage
        self.tip_amount = self.bill_amount * (self.tip_percentage / 100)
        self.bill_total = self.bill_amount + self.tip_amount
        self.tip_rounded_amount = self._calculate_rounded_tip()
        self.bill_total_rounded = self.bill_amount + self.tip_rounded_amount

    def _calculate_rounded_tip(self) -> float:
        rounded_total_amount = math.ceil(self.bill_total)
        rounded_tip_amount = rounded_total_amount - self.bill_amount
        return rounded_tip_amount


class TipCalc(LancoCog, name="TipCalc", description="TipCalc cog"):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.client = openai.Client(api_key=os.getenv("OPENAI_API_KEY"))
        self.cache_dir = os.path.join(self.get_cog_data_directory(), "Cache")
        self.file_downloader = FileDownloader()

    @commands.hybrid_command()
    async def tip(
        self, ctx: commands.Context, bill_amount: str = None, tip_percentage: str = None
    ):
        is_slash_command = ctx.interaction is not None

        def prompt_for_bill_amount(m: Message):
            return m.author == ctx.author and m.channel == ctx.channel

        response_embed = Embed(
            title="Tip Calculator",
            description="Calculating tip suggestions...",
            color=0x00FF00,
        )

        response_msg = None

        if bill_amount is None:
            try:
                await ctx.send(
                    f"{ctx.author.mention} Enter the bill amount or submit a photo of the receipt."
                )
                prompt_msg = await self.bot.wait_for(
                    "message", check=prompt_for_bill_amount, timeout=30
                )

                # first check to see if the user uploaded an image
                if prompt_msg.attachments:
                    response_embed = Embed(
                        title="Processing Image",
                        description="Please wait while I process the image...",
                        color=0x00FF00,
                    )
                    response_msg = await prompt_msg.reply(embed=response_embed)
                    bill_amount = await self.get_bill_total_from_image(prompt_msg)
                    if bill_amount is None:
                        response_embed = Embed(
                            title="Error",
                            description="Error processing the image. Please try again.",
                            color=0xFF0000,
                        )
                        await response_msg.edit(embed=response_embed)
                        return
                else:
                    bill_amount = prompt_msg.content
            except Exception as e:
                response_embed = Embed(
                    title="Error",
                    description="Timed out. Please try again.",
                    color=0xFF0000,
                )
                if response_msg:
                    await response_msg.edit(embed=response_embed)
                else:
                    await ctx.send(embed=response_embed)
                return

        if not isinstance(bill_amount, float):
            try:
                bill_amount = float(bill_amount.replace("$", ""))
            except ValueError:
                await ctx.send("Please provide a valid bill amount.")
                return

        valid_tip_perc = False
        try:
            if tip_percentage is not None:
                tip_percentage = float(tip_percentage.replace("$", ""))
                valid_tip_perc = True
        except ValueError:
            await ctx.send("Please provide a valid tip percentage.")
            return

        tip_amounts = (
            [15, 20, 25] if tip_percentage is None else [float(tip_percentage)]
        )
        tip_suggestions = [TipSuggestion(bill_amount, tip) for tip in tip_amounts]

        response = f"Tip suggestions for a bill amount of **${bill_amount:.2f}**\n\n"
        for ts in tip_suggestions:
            response += f"**{ts.tip_percentage}%**\n"
            response += "----------------\n"
            response += f"Tip amount: **${ts.tip_amount:.2f}**\n"
            response += f"Bill total: **${ts.bill_total:.2f}**\n"
            if ts.bill_total != ts.bill_total_rounded:
                response += "\nWant to round tip up to nearest dollar?\n"
                response += f"Tip amount (rounded): **${ts.tip_rounded_amount:.2f}**\n"
                response += f"Bill total (rounded): **${ts.bill_total_rounded:.2f}**\n"
            response += "\n"

        if not valid_tip_perc:
            example = (
                f"Example: ```{self.bot.command_prefix}tip {bill_amount:.2f} 22```"
            )
            if is_slash_command:
                example = f"Example: ```/{ctx.command} {bill_amount:.2f} 22```"
            response += f"Tip: You can provide a custom tip percentage as the 2nd argument. {example}"
            response += "\n\n*Disclaimer: The tip suggestions are for reference only. Please tip responsibly.*"

        response_embed = Embed(
            title="Tip Calculator", description=response, color=0x00FF00
        )
        if response_msg:
            await response_msg.edit(embed=response_embed)
        else:
            await ctx.send(embed=response_embed)

    def encode_image(self, image_path: str):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    async def get_bill_total_from_image(self, message: Message) -> str:
        results = await self.file_downloader.download_attachments(
            message, self.cache_dir
        )

        if not results:
            return None

        filename = results[0].filename
        encoded = self.encode_image(filename)

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that responds in JSON.",
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "If this appears to be a screenshot of a receipt, please provide the bill amount in json format with the property 'bill_total'.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{encoded}"},
                        },
                    ],
                },
            ],
            temperature=0.0,
        )

        # cleanup
        for r in results:
            os.remove(r.filename)

        response = response.choices[0].message.content
        print(response)
        # remove markdown
        response = response.replace("```json\n", "").replace("```", "")

        try:
            json_parsed = json.loads(response)
            total = json_parsed["bill_total"]
            self.logger.info(f"Bill total: {total}")
            return total

        except Exception as e:
            self.logger.error(f"Error parsing JSON: {e}")
            return None


async def setup(bot):
    await bot.add_cog(TipCalc(bot))
