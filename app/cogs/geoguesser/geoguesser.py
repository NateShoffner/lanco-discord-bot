import asyncio
import os
import re
import time
from math import floor

import aiofiles
import aiohttp
import discord
import googlemaps
from cogs.lancocog import RoundGameCog
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, View
from utils.command_utils import is_bot_owner
from utils.roundgame.dbmodels import RoundGameResult

from .dbmodels import SCORING_VERSION
from .dbmodels import GeoguesserLocation as LocationModel
from .locationutils import LocationUtils
from .models import Coordinates, GeoGuesserLocation, Mode, Round
from .session import GameSession

# module-level state — survives cog hot-reloads since the module itself is not reloaded
_active_sessions: dict = {}
_sessions_starting: list = []
_guess_semaphore = asyncio.Semaphore(4)


class GeoGuesser(
    RoundGameCog[GameSession],
    name="GeoGuesser",
    description="Lancaster-themed GeoGuesser game",
):
    GAME_NAME = "geoguesser"
    SCORING_VERSION = SCORING_VERSION
    GUESS_TIME = 20
    TIME_BETWEEN_ROUNDS = 10

    geoguesser_group = app_commands.Group(
        name="geoguesser", description="GeoGuesser commands"
    )

    city_mode = Mode(
        "Lancaster City",
        "🏙️",
        10000,
        (40.0382, -76.3055),
        re.compile(r"\blancaster city\b", re.IGNORECASE),
        "Lancaster City, PA",
        score_radius=2000,
    )
    county_mode = Mode(
        "Lancaster County",
        "🚜",
        30000,
        (40.0467, -76.1784),
        re.compile(r"\blancaster county\b", re.IGNORECASE),
        "Lancaster County, PA",
        score_radius=20000,
    )
    modes = [city_mode, county_mode]

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.gmaps = None
        self.location_utils = None
        self._ready_at: float = 0.0
        self.bot.database.create_tables([LocationModel, RoundGameResult])
        _sessions_starting.clear()

    async def cog_load(self):
        await super().cog_load()
        self._ready_at = time.time()
        self.gmaps = await asyncio.to_thread(
            googlemaps.Client, key=os.getenv("GMAPS_API_KEY")
        )
        self.location_utils = LocationUtils(self.gmaps)

    @property
    def active_sessions(self):
        return _active_sessions

    @property
    def sessions_starting(self):
        return _sessions_starting

    # ── RoundGameCog abstract implementations ─────────────────────────────────

    def should_record_guess(self, message: discord.Message) -> bool:
        guess = message.content.strip()
        return 3 <= len(guess) <= 100

    async def process_guess(
        self, session: GameSession, member: discord.Member, guess: str
    ):
        round_at_submit = session.current_round
        async with _guess_semaphore:
            result = await asyncio.to_thread(session.handle_guess, member, guess)
        if session.current_round != round_at_submit:
            return None
        if result:
            self.logger.info(
                f"{member} guessed '{guess}' — {result.distance:.0f}m away, score: {result.score:.1f}"
            )
        else:
            self.logger.info(f"{member} guess '{guess}' could not be resolved")
        return result

    async def build_round_embed(self, session: GameSession, intro: bool):
        current_round = session.get_current_round()
        cached_image_path = self.get_street_view_cache_path(current_round.location)

        if intro:
            title = f"GeoGuesser ({session.mode.icon} {session.mode.name})"
            description = (
                f"**{session.host.display_name}** has started a new game!\n\n"
                f"Guess the location shown in the photo.\n"
                f"Closer = more points.\n\n"
                f"**One guess per round.**\n"
                f"Your first response will be logged, so choose carefully.\n"
                f"✅ means your answer was recorded.\n\n"
                f"The host ({session.host.display_name}) can skip a round with `/geoguesser skip`."
            )
        else:
            title = f"Round {session.current_round + 1} of {len(session.rounds)}"
            description = None

        embed = discord.Embed(title=title, description=description, color=0x316CA3)
        embed.add_field(
            name="Round",
            value=f"{session.current_round + 1} / {len(session.rounds)}",
            inline=True,
        )
        embed.set_image(url="attachment://streetview.jpg")

        files = [discord.File(cached_image_path, filename="streetview.jpg")]
        return embed, files

    def build_results_embed(
        self, session: GameSession, next_round_time: int | None
    ) -> discord.Embed:
        r = session.get_current_round()
        coords = r.location.road_coords
        maps_url = f"https://www.google.com/maps?q={coords.lat},{coords.lng}"
        location_label = r.location.label or f"{coords.lat:.5f}, {coords.lng:.5f}"

        map_zoom = 16 if session.mode.score_radius <= 2000 else 13
        marker_colors = ["blue", "green", "purple", "orange", "yellow"]
        map_params = (
            f"center={coords.lat},{coords.lng}"
            f"&zoom={map_zoom}&size=600x300&maptype=roadmap"
            f"&markers=color:red%7Csize:large%7C{coords.lat},{coords.lng}"
        )
        sorted_guesses = sorted(r.guesses.items(), key=lambda x: x[1].distance)
        for i, (user_id, guess_result) in enumerate(sorted_guesses):
            if guess_result.guess_coords:
                color = marker_colors[i % len(marker_colors)]
                member = session.channel.guild.get_member(user_id)
                label = (member.display_name[0] if member else "?").upper()
                map_params += f"&markers=color:{color}%7Clabel:{label}%7C{guess_result.guess_coords.lat},{guess_result.guess_coords.lng}"
        static_map_url = f"https://maps.googleapis.com/maps/api/staticmap?{map_params}&key={os.getenv('GMAPS_API_KEY')}"

        def format_distance(meters: float) -> str:
            feet = meters * 3.28084
            if feet < 5280:
                return f"{feet:,.0f} ft"
            return f"{feet / 5280:.2f} mi"

        embed = discord.Embed(title="End of the round", color=0x316CA3)
        embed.add_field(
            name="Round", value=f"{r.number + 1} of {len(session.rounds)}", inline=True
        )
        embed.add_field(
            name="Answer", value=f"[{location_label}]({maps_url})", inline=True
        )

        if sorted_guesses:
            closest_id, closest_result = sorted_guesses[0]
            closest_member = session.channel.guild.get_member(closest_id)
            embed.add_field(
                name="Closest",
                value=f"`{closest_member.display_name}` ({format_distance(closest_result.distance)})",
                inline=True,
            )
            if len(sorted_guesses) > 1:
                furthest_id, furthest_result = sorted_guesses[-1]
                furthest_member = session.channel.guild.get_member(furthest_id)
                embed.add_field(
                    name="Furthest",
                    value=f"`{furthest_member.display_name}` ({format_distance(furthest_result.distance)})",
                    inline=True,
                )

        leaderboard = self.build_leaderboard(session)
        embed.add_field(name="Standings", value=leaderboard, inline=False)

        if next_round_time:
            embed.add_field(
                name="Next round", value=f"<t:{next_round_time}:R>", inline=False
            )

        embed.set_image(url=static_map_url)
        return embed

    def build_final_embed(self, session: GameSession) -> discord.Embed:
        leaderboard = self.build_leaderboard(session)
        winner = None
        if session.members:
            top_id = max(session.members, key=lambda uid: session.members[uid])
            if session.members[top_id] > 0:
                winner = session.channel.guild.get_member(top_id)

        title = f"{winner.display_name} wins!" if winner else "Game Over"
        description = f"{session.mode.icon} **{session.mode.name}** - {len(session.rounds)} rounds"
        embed = discord.Embed(title=title, description=description, color=0x316CA3)
        embed.add_field(name="Final Standings", value=leaderboard, inline=False)
        return embed

    async def on_game_end(self, session: GameSession):
        if len(session.members) > 1:
            with self.bot.database.atomic():
                for user_id, score in session.members.items():
                    RoundGameResult.create(
                        game_name=self.GAME_NAME,
                        game_id=session.game_id,
                        guild_id=session.channel.guild.id,
                        user_id=user_id,
                        mode=session.mode.name,
                        score=score,
                        rounds_played=len(session.rounds),
                        scoring_version=self.SCORING_VERSION,
                    )
            self.logger.info(
                f"Recorded results for game {session.game_id} — {len(session.members)} players"
            )

    # ── on_message ────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await self._handle_guess_message(message)

    # ── Session management ────────────────────────────────────────────────────

    async def _cleanup_stopped_session(self, session: GameSession):
        await super()._cleanup_stopped_session(session)

        r = session.get_current_round()
        if r and r.location:
            coords = r.location.road_coords
            maps_url = f"https://www.google.com/maps?q={coords.lat},{coords.lng}"
            location_label = r.location.label or f"{coords.lat:.5f}, {coords.lng:.5f}"
            # patch the already-sent embed to include the last answer
            # (base class sent the embed; we can't easily edit it here, so we send a follow-up)
            embed = discord.Embed(
                title="Last round answer",
                description=f"[{location_label}]({maps_url})",
                color=discord.Color.red(),
            )
            try:
                await session.channel.send(embed=embed)
            except discord.HTTPException:
                pass

    # ── Helpers ───────────────────────────────────────────────────────────────

    def get_street_view_cache_path(self, location: GeoGuesserLocation) -> str:
        cache_dir = os.path.join(self.get_cog_data_directory(), "streetview_cache")
        cached_image_path = os.path.join(cache_dir, f"{location.id}.jpg")
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        return cached_image_path

    async def load_locations_from_db(
        self, mode: Mode, count: int
    ) -> list[GeoGuesserLocation]:
        db_locations = (
            LocationModel.select()
            .where(LocationModel.mode == mode.name)
            .order_by(self.bot.database.random())
            .limit(count)
        )
        locations = []
        for location in db_locations:
            locations.append(
                GeoGuesserLocation(
                    Coordinates(location.initial_lat, location.initial_lng),
                    Coordinates(location.road_lat, location.road_lng),
                    id=location.id,
                    label=location.label,
                )
            )

        async def cache_image(location: GeoGuesserLocation):
            cached_image_path = self.get_street_view_cache_path(location)
            if not await asyncio.to_thread(os.path.exists, cached_image_path):
                street_view_url = self.location_utils.get_street_view_url(
                    location.road_coords
                )
                async with aiohttp.ClientSession() as s:
                    async with s.get(street_view_url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            async with aiofiles.open(cached_image_path, "wb") as f:
                                await f.write(data)

        await asyncio.gather(*[cache_image(loc) for loc in locations])
        return locations

    async def callback(self, interaction: discord.Interaction):
        mode_value = interaction.data["values"][0]
        mode = next((mode for mode in self.modes if mode.name == mode_value), None)
        channel = interaction.channel or await self.bot.fetch_channel(
            interaction.channel_id
        )

        available = (
            LocationModel.select().where(LocationModel.mode == mode.name).count()
        )
        if available == 0:
            await interaction.response.edit_message(
                content=f"No locations available for **{mode.name}**. A bot owner needs to run `/geoguesser populate` first.",
                view=None,
            )
            if interaction.channel_id in self.sessions_starting:
                self.sessions_starting.remove(interaction.channel_id)
            return

        round_choices = [5, 10, 15, 20]
        round_choices = [r for r in round_choices if r <= available]
        if not round_choices:
            round_choices = [available]

        rounds_select = Select(
            placeholder="How many rounds?",
            options=[
                discord.SelectOption(label=f"{r} rounds", value=str(r))
                for r in round_choices
            ],
        )

        async def rounds_callback(i: discord.Interaction):
            chosen_rounds = int(i.data["values"][0])
            await i.response.edit_message(
                content=f"Starting **{mode.name}** game ({chosen_rounds} rounds)...",
                view=None,
            )
            await self.initialize_session(mode, channel, i.user, rounds=chosen_rounds)

        rounds_select.callback = rounds_callback
        view = View(timeout=60)
        view.add_item(rounds_select)

        async def on_rounds_timeout():
            if interaction.channel_id in self.sessions_starting:
                self.sessions_starting.remove(interaction.channel_id)
            try:
                await interaction.edit_original_response(
                    content="Round selection timed out. Use `/geoguesser start` to try again.",
                    view=None,
                )
            except discord.HTTPException:
                pass

        view.on_timeout = on_rounds_timeout
        await interaction.response.edit_message(
            content=f"{mode.icon} **{mode.name}** selected ({available} locations available).",
            view=view,
        )

    def build_modes_select(self) -> Select:
        options = [
            discord.SelectOption(label=mode.name, emoji=mode.icon, value=mode.name)
            for mode in self.modes
        ]
        return Select(placeholder="Choose a Mode", options=options)

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.CommandInvokeError) and isinstance(
            error.original, discord.NotFound
        ):
            self.logger.debug(
                f"Interaction expired for command in #{interaction.channel_id}"
            )
            if interaction.channel_id in self.sessions_starting:
                self.sessions_starting.remove(interaction.channel_id)
            return
        raise error

    # ── Slash commands ────────────────────────────────────────────────────────

    @geoguesser_group.command(
        name="start", description="Start a new GeoGuesser session"
    )
    async def start(self, interaction: discord.Interaction):
        if self._is_stale_interaction(interaction):
            self.logger.debug(f"Discarding stale start interaction {interaction.id}")
            return
        if interaction.channel_id in self.active_sessions:
            await interaction.response.send_message("A session is already in progress")
            return
        if interaction.channel_id in self.sessions_starting:
            if interaction.channel_id not in self.active_sessions:
                self.sessions_starting.remove(interaction.channel_id)
            else:
                await interaction.response.send_message("A session is already starting")
                return

        self.sessions_starting.append(interaction.channel_id)

        try:
            select = self.build_modes_select()
            select.callback = self.callback

            view = View(timeout=60)
            view.add_item(select)

            async def on_timeout():
                if interaction.channel_id in self.sessions_starting:
                    self.sessions_starting.remove(interaction.channel_id)
                try:
                    await interaction.edit_original_response(
                        content="Mode selection timed out. Use `/geoguesser start` to try again.",
                        view=None,
                    )
                except discord.HTTPException:
                    pass

            view.on_timeout = on_timeout
            await interaction.response.send_message(view=view)
        except discord.NotFound:
            self.logger.debug(
                f"Start interaction expired before response (channel: {interaction.channel_id})"
            )
            if interaction.channel_id in self.sessions_starting:
                self.sessions_starting.remove(interaction.channel_id)
        except Exception:
            if interaction.channel_id in self.sessions_starting:
                self.sessions_starting.remove(interaction.channel_id)
            raise

    @geoguesser_group.command(
        name="stop", description="Stop the current GeoGuesser session"
    )
    async def stop(self, interaction: discord.Interaction):
        if self._is_stale_interaction(interaction):
            return
        session = self.get_session(interaction.channel_id)
        if not session:
            await interaction.response.send_message(
                "No session is in progress", ephemeral=True
            )
            return

        self.logger.info(
            f"Session stopped by {interaction.user} in #{interaction.channel} (guild: {interaction.guild}), "
            f"round {session.current_round + 1}/{len(session.rounds)}"
        )
        session.cancel()
        self.active_sessions.pop(interaction.channel_id, None)
        if interaction.channel_id in self.sessions_starting:
            self.sessions_starting.remove(interaction.channel_id)

        try:
            await interaction.response.send_message("Session stopped", ephemeral=True)
        except discord.HTTPException:
            pass

        asyncio.create_task(self._cleanup_stopped_session(session))

    @geoguesser_group.command(
        name="skip", description="Skips the current GeoGuesser round"
    )
    async def skip(self, interaction: discord.Interaction):
        if self._is_stale_interaction(interaction):
            return
        session = self.get_session(interaction.channel_id)
        if not session:
            await interaction.response.send_message(
                "No session is in progress", ephemeral=True
            )
            return
        if interaction.user != session.host:
            await interaction.response.send_message(
                "Only the host can skip the round", ephemeral=True
            )
            return
        if session.round_deadline == 0.0:
            await interaction.response.send_message(
                "Guessing is not currently active. Wait for the next round to start.",
                ephemeral=True,
            )
            return

        skipped_round = session.current_round + 1
        self.logger.info(
            f"Round {skipped_round}/{len(session.rounds)} skipped by {interaction.user} in #{interaction.channel}"
        )

        if session.round_task and not session.round_task.done():
            session.round_task.cancel()
        if session.warning_task and not session.warning_task.done():
            session.warning_task.cancel()

        session.round_deadline = 0.0

        if session.round_warning_message:
            try:
                await session.round_warning_message.delete()
            except discord.HTTPException:
                pass
            session.round_warning_message = None

        if session.has_next_round():
            session.next()
            next_round_time = int(time.time()) + self.TIME_BETWEEN_ROUNDS
            embed = discord.Embed(
                title=f"Round {skipped_round} skipped", color=0x316CA3
            )
            embed.add_field(
                name="Next round", value=f"<t:{next_round_time}:R>", inline=False
            )
            try:
                await interaction.response.send_message(embed=embed)
                session.skip_message = await interaction.original_response()
            except discord.HTTPException:
                session.skip_message = await session.channel.send(embed=embed)
            asyncio.create_task(self.post_current_round(session, immediate=False))
        else:
            try:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title=f"Round {skipped_round} skipped", color=0x316CA3
                    )
                )
            except discord.HTTPException:
                await session.channel.send(
                    embed=discord.Embed(
                        title=f"Round {skipped_round} skipped", color=0x316CA3
                    )
                )
            asyncio.create_task(self.post_final_results(session, skipped=True))

        if session.current_round_message:
            try:
                old = session.current_round_message.embeds[0]
                frozen = discord.Embed(
                    title=old.title, description=old.description, color=old.color.value
                )
                frozen.add_field(
                    name="Round",
                    value=f"{session.current_round} / {len(session.rounds)}",
                    inline=True,
                )
                frozen.add_field(name="Guessing closed", value="Skipped", inline=True)
                await session.current_round_message.edit(embed=frozen, attachments=[])
            except discord.HTTPException as e:
                self.logger.warning(f"Failed to freeze round embed on skip: {e}")

    @geoguesser_group.command(
        name="leaderboard",
        description="Show the GeoGuesser leaderboard for this server",
    )
    @app_commands.describe(period="Time period to filter by")
    @app_commands.choices(
        period=[
            app_commands.Choice(name="All Time", value="all"),
            app_commands.Choice(name="Today", value="today"),
            app_commands.Choice(name="This Week", value="week"),
        ]
    )
    async def leaderboard(self, interaction: discord.Interaction, period: str = "all"):
        import datetime

        guild_id = interaction.guild.id
        try:
            query = RoundGameResult.select().where(
                RoundGameResult.game_name == self.GAME_NAME,
                RoundGameResult.guild_id == guild_id,
                RoundGameResult.scoring_version == self.SCORING_VERSION,
            )
            list(query)
        except Exception as e:
            self.logger.error(f"Leaderboard query failed: {e}")
            await interaction.response.send_message(
                "Leaderboard unavailable. Run `poetry run migrate` to apply pending migrations.",
                ephemeral=True,
            )
            return

        now = datetime.datetime.utcnow()
        if period == "today":
            cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.where(RoundGameResult.played_at >= cutoff)
            period_label = "Today"
        elif period == "week":
            cutoff = now - datetime.timedelta(days=7)
            query = query.where(RoundGameResult.played_at >= cutoff)
            period_label = "This Week"
        else:
            period_label = "All Time"

        totals: dict[int, float] = {}
        for row in query:
            totals[row.user_id] = totals.get(row.user_id, 0) + row.score

        if not totals:
            embed = discord.Embed(
                title=f"GeoGuesser Leaderboard ({period_label})",
                description="No results recorded yet.\nGames require at least 2 players to count toward the leaderboard.",
                color=0x316CA3,
            )
            await interaction.response.send_message(embed=embed)
            return

        sorted_players = sorted(totals.items(), key=lambda x: x[1], reverse=True)
        lines = []
        for user_id, score in sorted_players[:10]:
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else f"<{user_id}>"
            lines.append(f"{len(lines) + 1}. `{name}` ({score:.0f})")

        embed = discord.Embed(
            title=f"GeoGuesser Leaderboard ({period_label})", color=0x316CA3
        )
        embed.add_field(name="Top Players", value="\n".join(lines), inline=False)
        embed.set_footer(
            text="Use /geoguesser leaderboard today or week to filter by period"
        )
        await interaction.response.send_message(embed=embed)

    @geoguesser_group.command(
        name="populate", description="Populate the database with locations"
    )
    @is_bot_owner()
    async def populate(self, interaction: discord.Interaction):
        select = self.build_modes_select()
        select.callback = self.population_callback
        view = View()
        view.add_item(select)
        await interaction.response.send_message(view=view)

    @geoguesser_group.command(name="wipe", description="Wipe all locations for a mode")
    @is_bot_owner()
    async def wipe(self, interaction: discord.Interaction):
        select = self.build_modes_select()

        async def wipe_callback(i: discord.Interaction):
            mode_value = i.data["values"][0]
            mode = next((m for m in self.modes if m.name == mode_value), None)
            deleted = (
                LocationModel.delete().where(LocationModel.mode == mode.name).execute()
            )
            self.logger.info(
                f"{i.user} wiped {deleted} locations for mode '{mode.name}'"
            )
            await i.response.send_message(
                f"Deleted **{deleted}** locations for **{mode.name}**.", ephemeral=True
            )

        select.callback = wipe_callback
        view = View()
        view.add_item(select)
        await interaction.response.send_message(view=view, ephemeral=True)

    @geoguesser_group.command(
        name="clearsessions", description="Clear all active and starting sessions"
    )
    @is_bot_owner()
    async def clearsessions(self, interaction: discord.Interaction):
        active = len(self.active_sessions)
        starting = len(self.sessions_starting)
        for session in self.active_sessions.values():
            session.cancel()
        self.active_sessions.clear()
        self.sessions_starting.clear()
        self.logger.info(
            f"Sessions cleared by {interaction.user} — {active} active, {starting} starting"
        )
        await interaction.response.send_message(
            f"Cleared {active} active and {starting} starting session(s).",
            ephemeral=True,
        )

    @geoguesser_group.command(
        name="stats", description="Show GeoGuesser database stats"
    )
    @is_bot_owner()
    async def stats(self, interaction: discord.Interaction):
        lines = []
        for mode in self.modes:
            count = (
                LocationModel.select().where(LocationModel.mode == mode.name).count()
            )
            labeled = (
                LocationModel.select()
                .where(
                    LocationModel.mode == mode.name, LocationModel.label.is_null(False)
                )
                .count()
            )
            lines.append(
                f"{mode.icon} **{mode.name}**: {count} locations ({labeled} labeled)"
            )

        games = (
            RoundGameResult.select(RoundGameResult.game_id)
            .where(RoundGameResult.game_name == self.GAME_NAME)
            .distinct()
            .count()
        )
        lines.append(f"\nGames recorded: **{games}**")

        embed = discord.Embed(
            title="GeoGuesser Stats", description="\n".join(lines), color=0x316CA3
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @geoguesser_group.command(
        name="seedleaderboard", description="Seed dummy leaderboard data for testing"
    )
    @is_bot_owner()
    async def seedleaderboard(self, interaction: discord.Interaction):
        import datetime
        import random
        import uuid

        members = [m for m in interaction.guild.members if not m.bot]
        if not members:
            await interaction.response.send_message("No members found.", ephemeral=True)
            return

        game_id = uuid.uuid4()
        with self.bot.database.atomic():
            for member in members:
                RoundGameResult.create(
                    game_name=self.GAME_NAME,
                    game_id=game_id,
                    guild_id=interaction.guild.id,
                    user_id=member.id,
                    mode=self.city_mode.name,
                    score=round(random.uniform(10, 500), 1),
                    rounds_played=10,
                    scoring_version=self.SCORING_VERSION,
                )

        await interaction.response.send_message(
            f"Seeded dummy results for {len(members)} members.", ephemeral=True
        )

    async def population_callback(self, interaction: discord.Interaction):
        mode_value = interaction.data["values"][0]
        mode = next((mode for mode in self.modes if mode.name == mode_value), None)

        await interaction.response.defer()

        count = 100
        self.logger.info(
            f"{interaction.user} started populating {count} locations for mode '{mode.name}'"
        )

        def make_progress_embed(description: str, color=0x316CA3) -> discord.Embed:
            return discord.Embed(
                title=f"Populating {mode.icon} {mode.name}",
                description=description,
                color=color,
            )

        progress_msg = await interaction.followup.send(
            embed=make_progress_embed(f"Generating **{count}** locations..."),
            wait=True,
            ephemeral=True,
        )

        try:
            import threading

            completed = {"count": 0, "last_label": ""}
            completed_lock = threading.Lock()

            def generate_and_save():
                import concurrent.futures

                import googlemaps
                from peewee import SqliteDatabase

                api_key = os.getenv("GMAPS_API_KEY")
                workers = min(count, 5)

                def generate_one(_):
                    client = googlemaps.Client(key=api_key)
                    utils = LocationUtils(client)
                    loc = utils.get_geoguesser_location_sync(mode)
                    with completed_lock:
                        completed["count"] += 1
                        completed["last_label"] = (
                            loc.label
                            or f"{loc.road_coords.lat:.4f}, {loc.road_coords.lng:.4f}"
                        )
                    self.logger.info(
                        f"Generated location {completed['count']}/{count} for '{mode.name}': {completed['last_label']}"
                    )
                    return loc

                with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                    locations = list(pool.map(generate_one, range(count)))

                thread_db = SqliteDatabase(os.getenv("SQLITE_DB"))
                thread_db.connect()
                LocationModel.bind(thread_db)
                try:
                    with thread_db.atomic():
                        LocationModel.delete().where(
                            LocationModel.mode == mode.name
                        ).execute()
                        for location in locations:
                            LocationModel.create(
                                mode=mode.name,
                                initial_lat=location.initial_location.lat,
                                initial_lng=location.initial_location.lng,
                                road_lat=location.road_coords.lat,
                                road_lng=location.road_coords.lng,
                                label=location.label,
                            )
                    return locations
                finally:
                    LocationModel.bind(self.bot.database)
                    thread_db.close()

            task = asyncio.create_task(asyncio.to_thread(generate_and_save))

            while not task.done():
                await asyncio.sleep(5)
                done = completed["count"]
                if done > 0 and not task.done():
                    try:
                        await progress_msg.edit(
                            embed=make_progress_embed(
                                f"Generating locations... **{done} / {count}** complete.\nLast: {completed['last_label']}"
                            )
                        )
                    except discord.HTTPException:
                        pass

            collected = await task
            labeled_count = sum(1 for l in collected if l.label)
            total = (
                LocationModel.select().where(LocationModel.mode == mode.name).count()
            )
            self.logger.info(
                f"Populate complete for '{mode.name}': {len(collected)} added ({labeled_count} labeled), {total} total"
            )
            embed = make_progress_embed(
                "Population complete.", color=discord.Color.green()
            )
            embed.add_field(
                name="Locations added", value=str(len(collected)), inline=True
            )
            embed.add_field(name="Street labels", value=str(labeled_count), inline=True)
            embed.add_field(name="Total in pool", value=str(total), inline=True)
            await progress_msg.edit(embed=embed)
        except Exception as e:
            self.logger.error(f"Populate failed for '{mode.name}': {e}", exc_info=True)
            await progress_msg.edit(
                embed=make_progress_embed(
                    f"Failed: ```{e}```", color=discord.Color.red()
                )
            )

    async def initialize_session(
        self,
        mode: Mode,
        channel: discord.TextChannel,
        host: discord.Member,
        rounds: int = 10,
    ):
        self.logger.info(
            f"Starting session in #{channel} (guild: {channel.guild}) — mode: {mode.name}, host: {host}, rounds: {rounds}"
        )
        try:
            session = GameSession(mode, channel, host, self.gmaps, self.location_utils)
            self.active_sessions[channel.id] = session
            locations = await self.load_locations_from_db(mode, rounds)
            self.logger.info(
                f"Loaded {len(locations)} locations for session in #{channel}"
            )
            if not locations:
                embed = discord.Embed(
                    title="No Locations Available",
                    description=(
                        f"There are no locations in the database for **{mode.name}**.\n\n"
                        f"A bot owner needs to run `/geoguesser populate` to add locations before a game can start."
                    ),
                    color=discord.Color.red(),
                )
                await channel.send(embed=embed)
                self.active_sessions.pop(channel.id, None)
                return
            rounds = [Round(i, loc) for i, loc in enumerate(locations)]
            session.init(rounds)
        except Exception as e:
            self.logger.error(
                f"Failed to initialize session in #{channel}: {e}", exc_info=True
            )
            self.active_sessions.pop(channel.id, None)
            await channel.send("Failed to start the session, please try again.")
            return
        finally:
            channel_id = channel.id if channel else None
            if channel_id and channel_id in self.sessions_starting:
                self.sessions_starting.remove(channel_id)

        asyncio.create_task(self.post_current_round(session, True, intro=True))


async def setup(bot):
    await bot.add_cog(GeoGuesser(bot))
