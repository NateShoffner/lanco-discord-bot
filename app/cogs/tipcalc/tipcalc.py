import mimetypes
import os

import discord
from cogs.lancocog import LancoCog
from discord import Embed, Message
from discord.ext import commands
from pydantic import BaseModel
from pydantic_ai import Agent, BinaryContent
from utils.ai_utils import run_agent
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


class CustomTipModal(discord.ui.Modal, title="Custom Tip"):
    percentage = discord.ui.TextInput(
        label="Tip Percentage",
        placeholder="e.g. 18",
        min_length=1,
        max_length=5,
    )

    def __init__(self, view: "TipView"):
        super().__init__()
        self.tip_view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            pct = float(self.percentage.value.replace("%", "").strip())
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid number.", ephemeral=True
            )
            return
        await self.tip_view.apply_custom_tip(interaction, pct)


class TipView(discord.ui.View):
    DEFAULT_PERCENTAGES = [15, 20, 25]

    def __init__(self, bill_amount: float):
        super().__init__(timeout=120)
        self.bill_amount = bill_amount
        self.suggestions = [
            TipSuggestion(bill_amount, pct) for pct in self.DEFAULT_PERCENTAGES
        ]
        self.custom_ts: TipSuggestion | None = None

    def build_embed(self) -> Embed:
        lines = [
            f"**{ts.tip_percentage:.0f}%** — ${ts.tip_amount:.2f} tip · **${ts.bill_total:.2f}** total"
            for ts in self.suggestions
        ]
        if self.custom_ts:
            ts = self.custom_ts
            lines.append(
                f"**{ts.tip_percentage:.0f}% (custom)** — ${ts.tip_amount:.2f} tip · **${ts.bill_total:.2f}** total"
            )
        return Embed(
            title="Tip Calculator",
            description=f"Suggestions for a bill of **${self.bill_amount:.2f}**\n\n"
            + "\n".join(lines),
            color=0x00FF00,
        )

    async def apply_custom_tip(self, interaction: discord.Interaction, pct: float):
        self.custom_ts = TipSuggestion(self.bill_amount, pct)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Custom Tip...", style=discord.ButtonStyle.secondary)
    async def custom_tip_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(CustomTipModal(self))


class TipCalc(LancoCog, name="TipCalc", description="Tip calculator commands"):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.agent = Agent(
            model="openai:gpt-5-nano",
            system_prompt="Describe this image.",
            output_type=BillDetails,
        )
        self.cache_dir = os.path.join(self.get_cog_data_directory(), "Cache")
        self.file_downloader = FileDownloader()

    @commands.hybrid_command()
    async def tip(self, ctx: commands.Context, bill_amount: str = None):
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

        view = TipView(bill_amount)

        if response_msg:
            await response_msg.edit(embed=view.build_embed(), view=view)
        else:
            await ctx.send(embed=view.build_embed(), view=view)

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

        result = await run_agent(
            lambda: self.agent.run(
                [
                    "Determine if this photo is a receipt and if so, parse out the bill details.",
                    BinaryContent(data=image_bytes, media_type=mime_type),
                ]
            ),
        )
        if result is None:
            return None

        # cleanup
        for r in results:
            os.remove(r.filename)

        return result.output


async def setup(bot):
    await bot.add_cog(TipCalc(bot))
