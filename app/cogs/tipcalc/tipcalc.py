import math

from cogs.lancocog import LancoCog
from discord import Embed
from discord.ext import commands


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

    @commands.hybrid_command()
    async def tip(
        self, ctx: commands.Context, bill_amount: str, tip_percentage: str = None
    ):
        try:
            bill_amount = float(bill_amount.replace("$", ""))
        except ValueError:
            await ctx.send("Please provide a valid bill amount.")
            return

        try:
            if tip_percentage is not None:
                tip_percentage = float(tip_percentage.replace("$", ""))
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

        response += f"Tip: You can provide a custom tip percentage as the 2nd argument. Example: ```{self.bot.command_prefix}tip {ts.bill_amount:.2f} 22```"

        embed = Embed(title="Tip Calculator", description=response, color=0x00FF00)

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(TipCalc(bot))
