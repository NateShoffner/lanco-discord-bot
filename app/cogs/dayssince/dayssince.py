"""
DaysSince Cog

Generic "X days since <thing>" counters. An admin defines a tracker and the
command name it answers to, and anyone can run that command to see how long it
has been, the running total, and the best streak so far.
"""

import datetime
import re

import discord
from cogs.lancocog import LancoCog
from discord import app_commands, ui
from discord.ext import commands
from utils.command_utils import is_bot_owner_or_admin
from utils.tracked_message import track_message_ids

from .models import DaysSinceTracker

COMMAND_NAME_PATTERN = re.compile(r"^[a-z0-9_-]{1,32}$")
TOTAL_PATTERN = re.compile(r"^\d{1,9}$")
MAX_LISTED = 25


def normalize_command_name(name: str) -> str:
    return name.strip().lstrip("!").lower()


def get_streak(tracker: DaysSinceTracker) -> int | None:
    """Whole days since the last occurrence, or None if nothing is recorded."""
    if not tracker.last_event_at:
        return None
    return (datetime.datetime.now() - tracker.last_event_at).days


def get_record(tracker: DaysSinceTracker) -> int:
    """The best streak, including one that is still running."""
    streak = get_streak(tracker)
    if streak is None:
        return tracker.record_days
    return max(tracker.record_days, streak)


class TrackerModal(ui.Modal, title="Days Since Tracker"):
    command_name = ui.TextInput(
        label="Command Name:",
        placeholder="coffeespill",
        style=discord.TextStyle.short,
        max_length=32,
        required=True,
    )

    tracker_title = ui.TextInput(
        label="Title:",
        placeholder="Office Coffee Machine",
        style=discord.TextStyle.short,
        max_length=100,
        required=True,
    )

    event_label = ui.TextInput(
        label="Event:",
        placeholder="coffee spill",
        style=discord.TextStyle.short,
        max_length=100,
        required=True,
    )

    total_count = ui.TextInput(
        label="Total:",
        placeholder="0",
        style=discord.TextStyle.short,
        max_length=9,
        required=False,
    )

    channel_selection = ui.Label(
        text="Restrict to Channel (Optional):",
        description="Limit the command to a single channel.",
        component=ui.ChannelSelect(
            channel_types=[discord.ChannelType.text], required=False
        ),
    )

    def __init__(self, tracker: DaysSinceTracker = None):
        super().__init__(timeout=None)
        self.tracker = tracker
        if tracker:
            self.command_name.default = tracker.command_name
            self.tracker_title.default = tracker.title
            self.event_label.default = tracker.event_label
            self.total_count.default = str(tracker.total_count)
            if tracker.channel_id:
                self.channel_selection.component.default_values = [
                    discord.Object(id=tracker.channel_id)
                ]

    async def on_submit(self, interaction: discord.Interaction) -> None:
        edit = self.tracker is not None
        command_name = normalize_command_name(self.command_name.value)

        if not COMMAND_NAME_PATTERN.match(command_name):
            await interaction.response.send_message(
                "Command names must be 1-32 characters of letters, numbers, "
                "dashes, or underscores, with no spaces.",
                ephemeral=True,
            )
            return

        total_raw = self.total_count.value.strip()
        if total_raw and not TOTAL_PATTERN.match(total_raw):
            await interaction.response.send_message(
                "Total must be a whole number of 0 or more.", ephemeral=True
            )
            return

        # A rename onto a name already in use would otherwise trip the unique
        # index and surface as a bare IntegrityError.
        existing = DaysSinceTracker.get_or_none(
            guild_id=interaction.guild_id, command_name=command_name
        )
        if existing and (not edit or existing.id != self.tracker.id):
            await interaction.response.send_message(
                f"A tracker named `{command_name}` already exists.", ephemeral=True
            )
            return

        tracker = self.tracker or DaysSinceTracker(guild_id=interaction.guild_id)
        tracker.command_name = command_name
        tracker.title = self.tracker_title.value.strip()
        tracker.event_label = self.event_label.value.strip()

        # Blank leaves the running total alone: on create the model default of 0
        # stands, and on edit a cleared field must not wipe the history. An
        # explicit reset to zero is `/dayssince set <name> total:0`.
        if total_raw:
            tracker.total_count = int(total_raw)

        if self.channel_selection.component.values:
            tracker.channel_id = self.channel_selection.component.values[0].id
        else:
            tracker.channel_id = None

        tracker.author = interaction.user.id
        tracker.last_updated = discord.utils.utcnow()
        tracker.save()

        prefix = interaction.client.get_guild_prefix(interaction.guild)

        embed = discord.Embed(
            title="Tracker Updated" if edit else "Tracker Created",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Command", value=f"{prefix}{command_name}", inline=False)
        embed.add_field(name="Title", value=tracker.title, inline=False)
        embed.add_field(name="Event", value=tracker.event_label, inline=False)
        embed.add_field(name="Total", value=str(tracker.total_count), inline=False)
        if tracker.channel_id:
            embed.add_field(
                name="Channel", value=f"<#{tracker.channel_id}>", inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class DaysSince(
    LancoCog,
    name="DaysSince",
    description="Track how long it has been since something last happened",
):
    g = app_commands.Group(
        name="dayssince",
        description="Manage days-since trackers",
        guild_only=True,
    )

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    async def cog_load(self):
        await super().cog_load()
        self.bot.database.create_tables([DaysSinceTracker])

    def get_tracker(self, guild_id: int, name: str) -> DaysSinceTracker | None:
        return DaysSinceTracker.get_or_none(
            guild_id=guild_id, command_name=normalize_command_name(name)
        )

    async def tracker_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        trackers = (
            DaysSinceTracker.select()
            .where(DaysSinceTracker.guild_id == interaction.guild_id)
            .order_by(DaysSinceTracker.command_name)
        )
        return [
            app_commands.Choice(name=t.command_name, value=t.command_name)
            for t in trackers
            if current.lower() in t.command_name.lower()
        ][:25]

    async def send_not_found(self, interaction: discord.Interaction, name: str) -> None:
        await interaction.response.send_message(
            f"No tracker named `{normalize_command_name(name)}` in this server.",
            ephemeral=True,
        )

    def build_status_embed(self, tracker: DaysSinceTracker) -> discord.Embed:
        streak = get_streak(tracker)

        if streak is None:
            description = f"No {tracker.event_label} recorded yet."
            color = discord.Color.greyple()
        else:
            unit = "day" if streak == 1 else "days"
            description = f"**{streak} {unit}** since the last {tracker.event_label}."
            if streak == 0:
                color = discord.Color.red()
            elif streak < 7:
                color = discord.Color.orange()
            else:
                color = discord.Color.green()

        embed = discord.Embed(title=tracker.title, description=description, color=color)
        embed.add_field(name="Total", value=str(tracker.total_count))
        embed.add_field(name="Record", value=f"{get_record(tracker)} days")
        if tracker.last_event_at:
            timestamp = int(tracker.last_event_at.timestamp())
            embed.add_field(
                name="Last occurrence", value=f"<t:{timestamp}:R>", inline=False
            )
        return embed

    @g.command(name="create", description="Create a days-since tracker")
    @is_bot_owner_or_admin()
    async def create(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TrackerModal())

    @g.command(name="edit", description="Edit a days-since tracker")
    @app_commands.describe(name="The tracker's command name")
    @is_bot_owner_or_admin()
    async def edit(self, interaction: discord.Interaction, name: str):
        tracker = self.get_tracker(interaction.guild_id, name)
        if not tracker:
            await self.send_not_found(interaction, name)
            return
        await interaction.response.send_modal(TrackerModal(tracker=tracker))

    @g.command(name="delete", description="Delete a days-since tracker")
    @app_commands.describe(name="The tracker's command name")
    @is_bot_owner_or_admin()
    async def delete(self, interaction: discord.Interaction, name: str):
        tracker = self.get_tracker(interaction.guild_id, name)
        if not tracker:
            await self.send_not_found(interaction, name)
            return

        tracker.delete_instance()
        await interaction.response.send_message(
            f"Deleted tracker `{tracker.command_name}`.", ephemeral=True
        )

    @g.command(
        name="incident", description="Record an occurrence, resetting the counter"
    )
    @app_commands.describe(name="The tracker's command name")
    @is_bot_owner_or_admin()
    async def incident(self, interaction: discord.Interaction, name: str):
        tracker = self.get_tracker(interaction.guild_id, name)
        if not tracker:
            await self.send_not_found(interaction, name)
            return

        streak = get_streak(tracker)
        broke_record = streak is not None and streak > tracker.record_days
        if broke_record:
            tracker.record_days = streak

        tracker.total_count += 1
        tracker.last_event_at = datetime.datetime.now()
        tracker.last_updated = discord.utils.utcnow()
        tracker.save()

        lines = [f"It has been **0 days** since the last {tracker.event_label}."]
        if streak is not None:
            unit = "day" if streak == 1 else "days"
            lines.append(f"The previous streak lasted **{streak} {unit}**.")
            if broke_record:
                lines.append("That is a new record.")
        lines.append(f"Total: **{tracker.total_count}**")

        embed = discord.Embed(
            title=tracker.title,
            description="\n".join(lines),
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed)

    @g.command(name="set", description="Correct a tracker's numbers")
    @app_commands.describe(
        name="The tracker's command name",
        days="Days since the last occurrence",
        total="Total number of occurrences",
        record="Longest streak without an occurrence, in days",
    )
    @is_bot_owner_or_admin()
    async def set_values(
        self,
        interaction: discord.Interaction,
        name: str,
        days: app_commands.Range[int, 0] = None,
        total: app_commands.Range[int, 0] = None,
        record: app_commands.Range[int, 0] = None,
    ):
        tracker = self.get_tracker(interaction.guild_id, name)
        if not tracker:
            await self.send_not_found(interaction, name)
            return

        if days is None and total is None and record is None:
            await interaction.response.send_message(
                "Give me at least one of `days`, `total`, or `record` to set.",
                ephemeral=True,
            )
            return

        changes = []
        if days is not None:
            tracker.last_event_at = datetime.datetime.now() - datetime.timedelta(
                days=days
            )
            changes.append(f"days -> **{days}**")
        if total is not None:
            tracker.total_count = total
            changes.append(f"total -> **{total}**")
        if record is not None:
            tracker.record_days = record
            changes.append(f"record -> **{record} days**")

        tracker.last_updated = discord.utils.utcnow()
        tracker.save()

        await interaction.response.send_message(
            f"Updated `{tracker.command_name}`: " + ", ".join(changes), ephemeral=True
        )

    @g.command(name="list", description="List this server's days-since trackers")
    async def list_trackers(self, interaction: discord.Interaction):
        trackers = list(
            DaysSinceTracker.select()
            .where(DaysSinceTracker.guild_id == interaction.guild_id)
            .order_by(DaysSinceTracker.command_name)
        )

        if not trackers:
            await interaction.response.send_message(
                "No trackers yet. Create one with `/dayssince create`.", ephemeral=True
            )
            return

        prefix = self.bot.get_guild_prefix(interaction.guild)
        embed = discord.Embed(
            title=f"Days Since Trackers ({len(trackers)})",
            color=discord.Color.blue(),
        )

        for tracker in trackers[:MAX_LISTED]:
            streak = get_streak(tracker)
            status = (
                "Nothing recorded yet"
                if streak is None
                else f"{streak} days since the last {tracker.event_label}"
            )
            value = (
                f"{tracker.title}\n{status} · "
                f"total {tracker.total_count} · record {get_record(tracker)}"
            )
            if tracker.channel_id:
                value += f"\nOnly in <#{tracker.channel_id}>"
            embed.add_field(
                name=f"{prefix}{tracker.command_name}", value=value, inline=False
            )

        if len(trackers) > MAX_LISTED:
            embed.set_footer(text=f"Showing {MAX_LISTED} of {len(trackers)} trackers")

        await interaction.response.send_message(embed=embed)

    edit.autocomplete("name")(tracker_autocomplete)
    delete.autocomplete("name")(tracker_autocomplete)
    incident.autocomplete("name")(tracker_autocomplete)
    set_values.autocomplete("name")(tracker_autocomplete)

    @commands.Cog.listener()
    @track_message_ids()
    async def on_message(self, message: discord.Message) -> discord.Message:
        if message.author.bot or message.guild is None:
            return None

        prefix = self.bot.get_guild_prefix(message.guild)
        if not message.content.startswith(prefix):
            return None

        command_name = message.content[len(prefix) :].strip().lower()
        if not command_name:
            return None

        tracker = DaysSinceTracker.get_or_none(
            guild_id=message.guild.id, command_name=command_name
        )
        if not tracker:
            return None

        if tracker.channel_id is not None and tracker.channel_id != message.channel.id:
            return None

        self.record_activity(f"dayssince:{command_name}", guild_id=message.guild.id)

        return await message.channel.send(embed=self.build_status_embed(tracker))


async def setup(bot):
    await bot.add_cog(DaysSince(bot))
