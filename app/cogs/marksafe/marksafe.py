import os

import discord
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from utils.command_utils import is_bot_owner_or_admin

from .models import MarkSafeConfig, MarkSafeEvent, MarkSafeUser


class MarkSafeModal(discord.ui.Modal, title="Event Details"):
    name_input = discord.ui.TextInput(
        label="Name:",
        placeholder="Name",
        style=discord.TextStyle.short,
        required=True,
    )

    description_input = discord.ui.TextInput(
        label="Description:",
        placeholder="Description",
        style=discord.TextStyle.long,
        required=True,
    )

    def __init__(self, event: MarkSafeEvent = None):
        super().__init__(timeout=None)
        self.event = event
        if event:
            self.name_input.default = event.name
            self.description_input.default = event.description

    async def on_submit(self, interaction: discord.Interaction) -> None:
        edit = self.event is not None

        if not edit:
            event, created = await MarkSafeEvent.get_or_create(
                guild_id=interaction.guild_id,
                name=self.name_input.value,
                description=self.description_input.value,
            )
            if not created:
                await interaction.response.send_message(
                    f"You already have a profile with the name {self.name}",
                    ephemeral=True,
                )
                return
            self.event = event

        self.event.name = self.name_input.value
        self.event.description = self.description_input.value
        await self.event.save()

        await interaction.response.send_message(
            f"{'Updated' if edit else 'Created'} event {self.event.name}"
        )


class MarkSafe(LancoCog, name="MarkSafe", description="Mark yourself as safe"):
    g = app_commands.Group(name="marksafe", description="Mark yourself as safe")

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.assets_dir = os.path.join(self.get_cog_data_directory(), "Assets")
        if not os.path.exists(self.assets_dir):
            os.makedirs(self.assets_dir)

    @commands.command(name="markunsafe", aliases=["unsafe", "unsafehere"])
    async def markunsafe(self, ctx: commands.Context):
        """Mark yourself as unsafe"""

        event = await MarkSafeEvent.get_or_none(guild_id=ctx.guild.id, active=True)

        if not event:
            await ctx.send("No active events")
            return

        user = await MarkSafeUser.get_or_none(
            user_id=ctx.author.id,
            guild_id=ctx.guild.id,
            event_id=event.id,
        )

        if not user:
            await ctx.send("You are already marked as unsafe")
            return

        await user.delete()

        embed = discord.Embed(title=event.name)
        embed.description = (
            f"{ctx.author.mention} is marked as unsafe from the **{event.name}**"
        )
        await ctx.send(embed=embed)

    @commands.command(name="marksafe", aliases=["safe", "safehere"])
    async def marksafe(self, ctx: commands.Context):
        """Mark yourself as safe"""

        event = await MarkSafeEvent.get_or_none(guild_id=ctx.guild.id, active=True)

        if not event:
            await ctx.send("No active events")
            return

        user = await MarkSafeUser.get_or_none(
            user_id=ctx.author.id,
            guild_id=ctx.guild.id,
            event_id=event.id,
        )

        if user:
            await ctx.send("You are already marked as safe")
            return

        await MarkSafeUser.create(
            user_id=ctx.author.id, guild_id=ctx.guild.id, event_id=event.id
        )

        flag_icon = os.path.join(self.assets_dir, "flag.png")
        file = discord.File(flag_icon, filename="flag.png")

        embed = discord.Embed(title=event.name)
        embed.description = (
            f"{ctx.author.mention} is marked as safe from the **{event.name}**"
        )
        embed.set_thumbnail(url="attachment://flag.png")
        await ctx.send(file=file, embed=embed)

    @g.command(name="create", description="Create a new event")
    @is_bot_owner_or_admin()
    async def marksafe_create(self, interaction: discord.Interaction):
        modal = MarkSafeModal()
        await interaction.response.send_modal(modal)


async def setup(bot):
    await bot.add_cog(MarkSafe(bot))
