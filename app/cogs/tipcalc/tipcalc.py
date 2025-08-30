import math
import mimetypes
import os

from cogs.lancocog import LancoCog
from discord import Embed, Message
from discord.ext import commands
from pydantic import BaseModel
from pydantic_ai import Agent, BinaryContent
from utils.file_downloader import FileDownloader


class BillDetails(BaseModel):
    is_bill: bool
    bill_total: float


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


class TipCalc(LancoCog, name="TipCalc", description="Tip calculator commands"):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.agent = Agent(
            model="openai:gpt-4o",
            system_prompt="Describe this image.",
            output_type=BillDetails,
        )
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
                    bill_details = await self.get_bill_details_from_image(prompt_msg)
                    if bill_details is None:
                        response_embed = Embed(
                            title="Error",
                            description="Error processing the image. Please try again.",
                            color=0xFF0000,
                        )
                        await response_msg.edit(embed=response_embed)
                        return
                    bill_amount = bill_details.bill_total
                else:  # TODO can probably just also have the agent handle manual calc
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

    async def get_bill_details_from_image(self, message: Message) -> BillDetails:
        results = await self.file_downloader.download_attachments(
            message, self.cache_dir
        )

        if not results:
            return None

        filename = results[0].filename

        with open(filename, "rb") as f:
            image_bytes = f.read()

        # TODO might want to use python-magic so it's content-based
        mime_type, _ = mimetypes.guess_type(filename)

        # throw it out if it's not an image
        if not mime_type or not mime_type.startswith("image/"):
            self.logger.error(f"File {filename} is not an image.")
            return None

        result = await self.agent.run(
            [
                "Determine if this photo is a receipt and if so, parse out the bill details.",
                BinaryContent(data=image_bytes, media_type=mime_type),
            ]
        )

        # cleanup
        for r in results:
            os.remove(r.filename)

        return result.output


async def setup(bot):
    await bot.add_cog(TipCalc(bot))
