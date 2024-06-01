import datetime

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from peewee import fn
from utils.command_utils import is_bot_owner_or_admin

from .models import Fact


class FactModal(discord.ui.Modal, title="Fact Info"):
    fact_input = discord.ui.TextInput(
        label="Enter a fact:",
        style=discord.TextStyle.long,
        required=True,
    )

    def __init__(self, fact: Fact = None):
        super().__init__(timeout=None)
        self.fact = fact
        if fact:
            self.fact_input.default = fact.fact

    async def on_submit(self, interaction: discord.Interaction) -> None:
        edit = self.fact is not None
        if not edit:
            fact, created = Fact.get_or_create(
                author_id=interaction.user.id,
                guild_id=interaction.guild.id,
                fact=self.fact_input.value,
                last_modified=datetime.datetime.utcnow(),
            )
            self.fact = fact

        self.fact.fact = self.fact_input.value
        self.fact.last_modified = datetime.datetime.utcnow()
        self.fact.save()

        await interaction.response.send_message(
            "Fact added" if not edit else "Fact updated"
        )


class Facts(LancoCog):
    fact_group = app_commands.Group(name="fact", description="Fact commands")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot = bot
        self.bot.database.create_tables([Fact])

    def get_random_fact(self, guild_id: int = None) -> Fact:
        fact = (
            Fact.select()
            .where(Fact.guild_id == guild_id)
            .order_by(fn.Random())
            .limit(1)
            .first()
        )
        return fact

    @fact_group.command(name="add", description="Add a fact")
    @is_bot_owner_or_admin()
    async def add_fact(self, interaction: discord.Interaction, fact_id: int = None):
        fact = Fact.get_or_none(id=fact_id)

        if fact and fact.author_id != interaction.user.id:
            await interaction.response.send_message(
                "You can't edit someone else's fact"
            )
            return

        modal = FactModal(fact)
        await interaction.response.send_modal(modal)

    @commands.command(name="fact", description="Get a random fact")
    async def fact(self, ctx: commands.Context):
        fact = self.get_random_fact(ctx.guild.id)

        embed = discord.Embed(title="Random Fact")
        if not fact:
            embed.description = "No facts found"
        else:
            embed.description = fact.fact
            author = self.bot.get_user(fact.author_id)
            if author:
                embed.set_footer(text=f"Added by {author.display_name} | ID: {fact.id}")

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Facts(bot))
