"""
TechLanc Cog

Description:
Tech Lancaster updates
"""

import datetime as dt
import os
import re
import urllib

import aiohttp
import discord
import feedparser
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands, tasks
from pydantic import BaseModel, Field
from utils.command_utils import is_bot_owner_or_admin
from utils.date_utils import next_nth_weekday, relative_date_str

from .models import TechLancAllowedPoster, TechLancConfig, TechLancGuildConfig

CALENDAR_URL = "https://techlancaster.com/#calendar"
CACHE_TTL = dt.timedelta(hours=1)
TLM_RSS_URL = "https://www.meetup.com/tech-lancaster-meetups/events/rss/"
TLM_EVENT_TITLE = "Tech Lancaster Meetup"
TLM_TIME = "6:30PM"
DEFAULT_LOCATION_NAME = "West Art"
DEFAULT_LOCATION_URL = (
    "https://www.google.com/maps/search/?api=1&query=West+Art+Lancaster+PA"
)

PS_TIME = "6PM"
PS_DESCRIPTION = "Pub Standards Lancaster is a meetup of developers, designers, founders and people-who-like-to-build-stuff in central Pennsylvania. Pub Standards is open to everyone. It's loosely aimed at web design & development geeks, but that doesn't mean chitchat need necessarily be work-related. Don't expect structure, don't expect presentations, just relax with likeminded people and a few beers."
PS_DEFAULT_LOCATION_NAME = "Tellus"
PS_DEFAULT_LOCATION_URL = (
    "https://www.google.com/maps/search/?api=1&query=Tellus360+Lancaster+PA"
)
PS_DEFAULT_LOCATION_NOTES = "rooftop bar (if open), otherwise second floor"

DAY_CHOICES = [
    app_commands.Choice(name="Monday", value=0),
    app_commands.Choice(name="Tuesday", value=1),
    app_commands.Choice(name="Wednesday", value=2),
    app_commands.Choice(name="Thursday", value=3),
    app_commands.Choice(name="Friday", value=4),
    app_commands.Choice(name="Saturday", value=5),
    app_commands.Choice(name="Sunday", value=6),
]

DAY_NAMES = {c.value: c.name for c in DAY_CHOICES}


class Settings(BaseModel):
    api_key: str = Field(..., description="Google API key")
    calendar: str = Field(..., description="Calendar ID")
    lookahead_days: int = Field(7, ge=1, le=365)


class Meetup(BaseModel):
    id: str = Field(..., description="Meetup ID")
    name: str = Field(..., description="Meetup name")
    url: str = Field(..., description="Meetup URL")
    location: str = Field(..., description="Location of the meetup")
    description: str = Field(..., description="Description of the meetup")
    time_start: dt.datetime = Field(..., description="Start time of the meetup")
    time_end: dt.datetime = Field(..., description="End time of the meetup")


class TechLanc(
    LancoCog,
    name="TechLanc",
    description="Tech Lancaster updates",
):
    techlanc_group = app_commands.Group(
        name="techlanc", description="Tech Lancaster commands"
    )

    def __init__(self, bot):
        super().__init__(bot)
        self.settings = Settings(
            api_key=os.getenv("GOOGLE_CAL_API_KEY"),
            calendar="6l7e832ee9bemt1i9c42vltrug@group.calendar.google.com",
            lookahead_days=7,
        )
        self._cache: list[Meetup] = []
        self._cache_time: dt.datetime | None = None
        self._rss_cache = None
        self._rss_cache_time: dt.datetime | None = None

    async def cog_load(self):
        self.bot.database.create_tables(
            [TechLancConfig, TechLancGuildConfig, TechLancAllowedPoster]
        )
        self.scheduled_post.start()

    def cog_unload(self):
        self.scheduled_post.cancel()

    @tasks.loop(minutes=1)
    async def scheduled_post(self):
        now = dt.datetime.utcnow()
        configs = TechLancConfig.select()
        for config in configs:
            if (
                now.weekday() == config.day_of_week
                and now.hour == config.post_hour
                and now.minute == config.post_minute
            ):
                channel = self.bot.get_channel(config.channel_id)
                if channel:
                    await self.send_weekly_meetups(channel)

    @techlanc_group.command(
        name="setchannel",
        description="Enable weekly Tech Lancaster meetup posts in a channel",
    )
    @app_commands.describe(
        channel="Channel to post weekly meetup updates in",
        day="Day of the week to post (UTC)",
        hour="Hour to post (0-23, UTC)",
        minute="Minute to post (0-59, UTC)",
    )
    @app_commands.choices(day=DAY_CHOICES)
    @is_bot_owner_or_admin()
    async def set_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        day: app_commands.Choice[int],
        hour: app_commands.Range[int, 0, 23],
        minute: app_commands.Range[int, 0, 59],
    ):
        exists = TechLancConfig.get_or_none(
            TechLancConfig.guild_id == interaction.guild.id,
            TechLancConfig.channel_id == channel.id,
        )
        if exists:
            exists.day_of_week = day.value
            exists.post_hour = hour
            exists.post_minute = minute
            exists.save()
            await interaction.response.send_message(
                f"Updated schedule for {channel.mention}: {day.name}s at {hour:02d}:{minute:02d} UTC.",
                ephemeral=True,
            )
            return

        TechLancConfig.create(
            guild_id=interaction.guild.id,
            channel_id=channel.id,
            day_of_week=day.value,
            post_hour=hour,
            post_minute=minute,
        )
        await interaction.response.send_message(
            f"Weekly Tech Lancaster posts enabled in {channel.mention}: {day.name}s at {hour:02d}:{minute:02d} UTC.",
            ephemeral=True,
        )

    @techlanc_group.command(
        name="unsetchannel",
        description="Disable weekly Tech Lancaster meetup posts in a channel",
    )
    @app_commands.describe(channel="Channel to remove from weekly meetup posts")
    @is_bot_owner_or_admin()
    async def unset_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        deleted = (
            TechLancConfig.delete()
            .where(
                TechLancConfig.guild_id == interaction.guild.id,
                TechLancConfig.channel_id == channel.id,
            )
            .execute()
        )
        if deleted:
            await interaction.response.send_message(
                f"Weekly Tech Lancaster posts disabled in {channel.mention}.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"{channel.mention} was not configured.", ephemeral=True
            )

    @techlanc_group.command(
        name="list", description="List configured Tech Lancaster announcement channels"
    )
    @is_bot_owner_or_admin()
    async def list_channels(self, interaction: discord.Interaction):
        configs = TechLancConfig.select().where(
            TechLancConfig.guild_id == interaction.guild.id
        )
        if not configs:
            await interaction.response.send_message(
                "No channels configured.", ephemeral=True
            )
            return

        lines = []
        for config in configs:
            channel = interaction.guild.get_channel(config.channel_id)
            name = channel.mention if channel else f"#{config.channel_id}"
            day = DAY_NAMES.get(config.day_of_week, "?")
            lines.append(
                f"{name} — {day}s at {config.post_hour:02d}:{config.post_minute:02d} UTC"
            )

        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @techlanc_group.command(
        name="post", description="Manually post this week's Tech Lancaster meetups"
    )
    @is_bot_owner_or_admin()
    async def post(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.send_weekly_meetups(interaction.channel)
        await interaction.followup.send("Posted.", ephemeral=True)

    @techlanc_group.command(
        name="seteventurl",
        description="Set the Discord event URL to include in Tech Lancaster Meetup posts",
    )
    @app_commands.describe(
        url="Discord event URL for the upcoming Tech Lancaster Meetup"
    )
    @is_bot_owner_or_admin()
    async def set_event_url(self, interaction: discord.Interaction, url: str):
        if not url.startswith("https://discord.com/events/"):
            await interaction.response.send_message(
                "That doesn't look like a Discord event URL. Expected format: `https://discord.com/events/...`",
                ephemeral=True,
            )
            return
        config, _ = TechLancGuildConfig.get_or_create(guild_id=interaction.guild.id)
        config.discord_event_url = url
        config.save()
        await interaction.response.send_message(
            f"Discord event URL set: {url}", ephemeral=True
        )

    @techlanc_group.command(
        name="cleareventurl",
        description="Clear the Discord event URL from Tech Lancaster Meetup posts",
    )
    @is_bot_owner_or_admin()
    async def clear_event_url(self, interaction: discord.Interaction):
        config = TechLancGuildConfig.get_or_none(
            TechLancGuildConfig.guild_id == interaction.guild.id
        )
        if config and config.discord_event_url:
            config.discord_event_url = None
            config.save()
            await interaction.response.send_message(
                "Discord event URL cleared.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "No Discord event URL was set.", ephemeral=True
            )

    @techlanc_group.command(
        name="eventurl",
        description="Show the currently configured Discord event URL",
    )
    @is_bot_owner_or_admin()
    async def show_event_url(self, interaction: discord.Interaction):
        config = TechLancGuildConfig.get_or_none(
            TechLancGuildConfig.guild_id == interaction.guild.id
        )
        if config and config.discord_event_url:
            await interaction.response.send_message(
                f"Current Discord event URL: {config.discord_event_url}", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "No Discord event URL is currently set.", ephemeral=True
            )

    @techlanc_group.command(
        name="setpingrole",
        description="Set the role to ping in Tech Lancaster Meetup posts",
    )
    @app_commands.describe(role="Role to ping at the start of meetup posts")
    @is_bot_owner_or_admin()
    async def set_ping_role(self, interaction: discord.Interaction, role: discord.Role):
        config, _ = TechLancGuildConfig.get_or_create(guild_id=interaction.guild.id)
        config.ping_role_id = role.id
        config.save()
        await interaction.response.send_message(
            f"Ping role set to {role.mention}.", ephemeral=True
        )

    @techlanc_group.command(
        name="clearpingrole",
        description="Clear the role ping from Tech Lancaster Meetup posts",
    )
    @is_bot_owner_or_admin()
    async def clear_ping_role(self, interaction: discord.Interaction):
        config = TechLancGuildConfig.get_or_none(
            TechLancGuildConfig.guild_id == interaction.guild.id
        )
        if config and config.ping_role_id:
            config.ping_role_id = None
            config.save()
            await interaction.response.send_message(
                "Ping role cleared.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "No ping role was set.", ephemeral=True
            )

    @techlanc_group.command(
        name="setlocation",
        description="Set the location name and URL for Tech Lancaster Meetup posts",
    )
    @app_commands.describe(
        name="Display name for the location (e.g. West Art)",
        url="Google Maps or website URL for the location",
    )
    @is_bot_owner_or_admin()
    async def set_location(self, interaction: discord.Interaction, name: str, url: str):
        config, _ = TechLancGuildConfig.get_or_create(guild_id=interaction.guild.id)
        config.location_name = name
        config.location_url = url
        config.save()
        await interaction.response.send_message(
            f"Location set to [{name}]({url}).", ephemeral=True
        )

    @techlanc_group.command(
        name="resetlocation",
        description="Reset the location back to the default (West Art)",
    )
    @is_bot_owner_or_admin()
    async def reset_location(self, interaction: discord.Interaction):
        config, _ = TechLancGuildConfig.get_or_create(guild_id=interaction.guild.id)
        config.location_name = DEFAULT_LOCATION_NAME
        config.location_url = DEFAULT_LOCATION_URL
        config.save()
        await interaction.response.send_message(
            f"Location reset to [{DEFAULT_LOCATION_NAME}]({DEFAULT_LOCATION_URL}).",
            ephemeral=True,
        )

    # --- Pub Standards ---

    # TODO: replace with a custom command once the CustomCommands cog supports dynamic date formatting
    @commands.command(name="ps")
    async def ps_command(self, ctx):
        """Post the Pub Standards meetup announcement."""
        if not self._can_post_tlm(ctx):
            await ctx.send(
                "You don't have permission to use this command.", delete_after=10
            )
            return

        guild_config = (
            TechLancGuildConfig.get_or_none(
                TechLancGuildConfig.guild_id == ctx.guild.id
            )
            if ctx.guild
            else None
        )
        ping_role_id = guild_config.ping_role_id if guild_config else None

        event_date = next_nth_weekday(dt.date.today(), weekday=3, n=2)
        when = relative_date_str(event_date)
        role_ping = f"<@&{ping_role_id}> " if ping_role_id else ""
        location_part = f"[{PS_DEFAULT_LOCATION_NAME}](<{PS_DEFAULT_LOCATION_URL}>), {PS_DEFAULT_LOCATION_NOTES}"
        intro = f"{role_ping}Pub Standards meetup **{when}** at {location_part} @ {PS_TIME}."
        await ctx.send(f"{intro}\n\n{PS_DESCRIPTION}")

    @commands.command(name="tl", aliases=["techlanc", "techlancaster"])
    async def tl_command(self, ctx):
        """Post this week's Tech Lancaster meetups."""
        await self.send_weekly_meetups(ctx.channel)

    @techlanc_group.command(
        name="addposter",
        description="Allow a user or role to use !tlm",
    )
    @app_commands.describe(user="User to allow", role="Role to allow")
    @is_bot_owner_or_admin()
    async def add_poster(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None,
        role: discord.Role = None,
    ):
        if not user and not role:
            await interaction.response.send_message(
                "Provide a user or role.", ephemeral=True
            )
            return

        if user:
            exists = TechLancAllowedPoster.get_or_none(
                TechLancAllowedPoster.guild_id == interaction.guild.id,
                TechLancAllowedPoster.user_id == user.id,
            )
            if not exists:
                TechLancAllowedPoster.create(
                    guild_id=interaction.guild.id, user_id=user.id
                )

        if role:
            exists = TechLancAllowedPoster.get_or_none(
                TechLancAllowedPoster.guild_id == interaction.guild.id,
                TechLancAllowedPoster.role_id == role.id,
            )
            if not exists:
                TechLancAllowedPoster.create(
                    guild_id=interaction.guild.id, role_id=role.id
                )

        label = " and ".join(
            filter(
                None, [user.mention if user else None, role.mention if role else None]
            )
        )
        await interaction.response.send_message(
            f"Added {label} as allowed poster(s).", ephemeral=True
        )

    @techlanc_group.command(
        name="removeposter",
        description="Remove a user or role from the !tlm allowed list",
    )
    @app_commands.describe(user="User to remove", role="Role to remove")
    @is_bot_owner_or_admin()
    async def remove_poster(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None,
        role: discord.Role = None,
    ):
        if not user and not role:
            await interaction.response.send_message(
                "Provide a user or role.", ephemeral=True
            )
            return

        deleted = 0
        if user:
            deleted += (
                TechLancAllowedPoster.delete()
                .where(
                    TechLancAllowedPoster.guild_id == interaction.guild.id,
                    TechLancAllowedPoster.user_id == user.id,
                )
                .execute()
            )
        if role:
            deleted += (
                TechLancAllowedPoster.delete()
                .where(
                    TechLancAllowedPoster.guild_id == interaction.guild.id,
                    TechLancAllowedPoster.role_id == role.id,
                )
                .execute()
            )

        if deleted:
            label = " and ".join(
                filter(
                    None,
                    [user.mention if user else None, role.mention if role else None],
                )
            )
            await interaction.response.send_message(
                f"Removed {label} from allowed posters.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "No matching entries found.", ephemeral=True
            )

    @techlanc_group.command(
        name="listposters",
        description="List users and roles allowed to use !tlm",
    )
    @is_bot_owner_or_admin()
    async def list_posters(self, interaction: discord.Interaction):
        entries = TechLancAllowedPoster.select().where(
            TechLancAllowedPoster.guild_id == interaction.guild.id
        )
        if not entries:
            await interaction.response.send_message(
                "No allowed posters configured. Only admins can use !tlm.",
                ephemeral=True,
            )
            return

        lines = []
        for entry in entries:
            if entry.user_id:
                member = interaction.guild.get_member(entry.user_id)
                lines.append(
                    f"👤 {member.mention if member else f'<@{entry.user_id}>'}"
                )
            elif entry.role_id:
                role = interaction.guild.get_role(entry.role_id)
                lines.append(f"🏷️ {role.mention if role else f'<@&{entry.role_id}>'}")

        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    def _can_post_tlm(self, ctx: commands.Context) -> bool:
        """Returns True if the user is allowed to run !tlm."""
        # Bot owner and admins always can
        if ctx.author.guild_permissions.administrator:
            return True
        if ctx.guild is None:
            return False

        allowed = TechLancAllowedPoster.select().where(
            TechLancAllowedPoster.guild_id == ctx.guild.id
        )
        user_role_ids = {r.id for r in ctx.author.roles}
        for entry in allowed:
            if entry.user_id and entry.user_id == ctx.author.id:
                return True
            if entry.role_id and entry.role_id in user_role_ids:
                return True
        return False

    @commands.command(name="tlm")
    async def tlm_command(self, ctx):
        """Post the next Tech Lancaster Meetup details including speakers."""
        if not self._can_post_tlm(ctx):
            await ctx.send(
                "You don't have permission to use this command.", delete_after=10
            )
            return

        async with ctx.typing():
            entry = await self.get_next_tlm_entry()

        if not entry:
            await ctx.send("No upcoming Tech Lancaster Meetup found in the RSS feed.")
            return

        guild_config = (
            TechLancGuildConfig.get_or_none(
                TechLancGuildConfig.guild_id == ctx.guild.id
            )
            if ctx.guild
            else None
        )

        event_url = guild_config.discord_event_url if guild_config else None
        ping_role_id = guild_config.ping_role_id if guild_config else None
        location_name = (
            guild_config.location_name if guild_config else DEFAULT_LOCATION_NAME
        )
        location_url = (
            guild_config.location_url if guild_config else DEFAULT_LOCATION_URL
        )

        intro = self._build_tlm_intro(ping_role_id, location_name, location_url)
        body = self._format_tlm_description(
            entry.get("description", entry.get("summary", ""))
        )
        if event_url:
            body += f"\n\n{event_url}"

        full_message = f"{intro}\n\n{body}"

        # Split at 2000-char Discord limit if needed
        chunks = [full_message[i : i + 2000] for i in range(0, len(full_message), 2000)]
        for chunk in chunks:
            await ctx.send(chunk)

    async def send_weekly_meetups(self, channel: discord.TextChannel):
        meetups = await self.get_meetups()

        embed = discord.Embed(
            title="This Week's Tech Lancaster Meetups",
            color=discord.Color.blue(),
        )

        if meetups:
            lines = []
            for meetup in meetups:
                local = meetup.time_start.astimezone(dt.timezone.utc)
                day_abbr = local.strftime("%a")
                time_str = local.strftime("%I:%M%p").lstrip("0").upper()
                line = f"• {meetup.name} - {day_abbr} {time_str}"
                if self._is_physical_address(meetup.location):
                    encoded = urllib.parse.quote(meetup.location)
                    gmaps_url = (
                        f"https://www.google.com/maps/search/?api=1&query={encoded}"
                    )
                    line += f" ([📍 Map]({gmaps_url}))"
                lines.append(line)
            embed.description = "\n".join(lines)
        else:
            embed.description = "No meetups this week."

        embed.description += f"\n\nFor more info visit {CALENDAR_URL}"

        await channel.send(embed=embed)

    async def get_next_tlm_entry(self):
        """Fetch the RSS feed and return the most recent Tech Lancaster Meetup entry."""
        now = dt.datetime.utcnow()
        if (
            self._rss_cache
            and self._rss_cache_time
            and now - self._rss_cache_time < CACHE_TTL
        ):
            return self._rss_cache

        async with aiohttp.ClientSession() as session:
            async with session.get(TLM_RSS_URL) as resp:
                text = await resp.text()

        feed = feedparser.parse(text)
        entry = next(
            (
                e
                for e in feed.entries
                if TLM_EVENT_TITLE.lower() in e.get("title", "").lower()
            ),
            None,
        )
        self._rss_cache = entry
        self._rss_cache_time = now
        return entry

    def build_tlm_embeds(self, entry, event_url: str = None) -> list[discord.Embed]:
        """Build Discord embed(s) from a TLM RSS entry."""
        title = entry.get("title", TLM_EVENT_TITLE)
        link = entry.get("link", "")
        raw = entry.get("description", entry.get("summary", ""))

        body = self._format_tlm_description(raw)

        if event_url:
            body += f"\n\n[Join the Discord Event]({event_url})"

        # Discord embed description cap is 4096 chars — split if needed
        chunks = [body[i : i + 4096] for i in range(0, max(len(body), 1), 4096)]
        embeds = []
        for i, chunk in enumerate(chunks):
            embed = discord.Embed(
                title=title if i == 0 else None,
                url=link if i == 0 else None,
                description=chunk,
                color=discord.Color.blue(),
            )
            if i == len(chunks) - 1:
                embed.set_footer(text=link)
            embeds.append(embed)
        return embeds

    def _build_tlm_intro(
        self, ping_role_id: int | None, location_name: str, location_url: str
    ) -> str:
        """Build the plain-text intro line for a TLM post."""
        event_date = next_nth_weekday(dt.date.today(), weekday=3, n=4)
        when = relative_date_str(event_date)
        role_ping = f"<@&{ping_role_id}> " if ping_role_id else ""
        return f"{role_ping}It's Tech Lancaster **{when}** at {TLM_TIME} at [{location_name}](<{location_url}>)!"

    def _format_tlm_description(self, raw: str) -> str:
        """Clean up the RSS description for Discord markdown."""
        # Normalize line endings
        text = raw.replace("\r\n", "\n").replace("\r", "\n")

        # Ensure a blank line before each bold speaker line (**Name - *Talk***)
        text = re.sub(r"(?<!\n)\n(\*\*[^*])", r"\n\n\1", text)

        # Collapse 3+ blank lines to 2
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Strip bare Discord event URLs (they'll be injected as a proper link)
        text = re.sub(r"\nhttps://discord\.com/events/\S+", "", text)

        return text.strip()

    def _is_physical_address(self, location: str) -> bool:
        if not location:
            return False
        skip = {"online", "virtual", "zoom", "tbd", "tba", ""}
        if location.strip().lower() in skip:
            return False
        return any(c.isdigit() for c in location) or "," in location

    async def get_meetups(self) -> list[Meetup]:
        now = dt.datetime.utcnow()
        if self._cache and self._cache_time and now - self._cache_time < CACHE_TTL:
            return self._cache
        now_str = now.isoformat() + "Z"
        end_str = (
            now + dt.timedelta(days=self.settings.lookahead_days)
        ).isoformat() + "Z"

        url = (
            f"https://www.googleapis.com/calendar/v3/calendars/{self.settings.calendar}/events"
            f"?key={self.settings.api_key}"
            f"&timeMin={now_str}"
            f"&timeMax={end_str}"
            f"&singleEvents=true"
            f"&orderBy=startTime"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                events_result = await resp.json()

        event_items = events_result.get("items", [])
        if not event_items:
            self._cache = []
            self._cache_time = dt.datetime.utcnow()
            return []

        meetups = []
        for item in event_items:
            start_str = item["start"].get("dateTime", item["start"].get("date"))
            end_str = item["end"].get("dateTime", item["end"].get("date"))
            try:
                time_start = dt.datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            except Exception:
                time_start = dt.datetime.strptime(start_str, "%Y-%m-%d")
            try:
                time_end = dt.datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            except Exception:
                time_end = dt.datetime.strptime(end_str, "%Y-%m-%d")

            meetups.append(
                Meetup(
                    id=item.get("id", ""),
                    name=item.get("summary", "(No title)"),
                    url=item.get("htmlLink", ""),
                    location=item.get("location", ""),
                    description=item.get("description", ""),
                    time_start=time_start,
                    time_end=time_end,
                )
            )

        self._cache = meetups
        self._cache_time = now
        return meetups


async def setup(bot):
    await bot.add_cog(TechLanc(bot))
