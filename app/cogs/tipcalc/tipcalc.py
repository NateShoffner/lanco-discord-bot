from cogs.lancocog import LancoCog
from discord import Embed, app_commands
from discord.ext import commands


class TipCalc(LancoCog, name="TipCalc", description="TipCalc cog"):

    g = app_commands.Group(name="tipcalc", description="TipCalc commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    @commands.hybrid_command()
    async def tip(self, ctx: commands.Context, amount: str, round_tip: bool = False):
        try:
            amount = float(amount.replace("$", ""))
        except ValueError:
            await ctx.send("Invalid amount")
            return

        tip_suggestions = {
            15: amount * 0.15,
            20: amount * 0.20,
            25: amount * 0.25,
            35: amount * 0.35,
        }

        response = "Tip suggestions:\n"

        for tip, tip_amount in tip_suggestions.items():
            if round_tip:
                rounded_total = self.calculate_rounded_tip(amount, tip)
                response += f"{tip}%: ${rounded_total:.2f}\n"
            else:
                response += f"{tip}%: ${tip_amount:.2f}\n"

        embed = Embed(title="Tip Calculator", description=response, color=0x00FF00)

        await ctx.send(embed=embed)

    def calculate_rounded_tip(self, amount: float, tip: float) -> float:
        tip_amount = amount * (tip / 100)
        total_with_tip = amount + tip_amount
        rounded_total = round(total_with_tip)
        return rounded_total


async def setup(bot):
    await bot.add_cog(TipCalc(bot))
