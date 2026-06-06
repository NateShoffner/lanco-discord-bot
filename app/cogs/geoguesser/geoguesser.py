import asyncio
import os
import re
import time
from math import floor

import aiohttp
import discord
import googlemaps
from cogs.lancocog import LancoCog
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, View
from utils.command_utils import is_bot_owner

from .dbmodels import GeoguesserGameResult
from .dbmodels import GeoguesserLocation as LocationModel
from .locationutils import LocationUtils
from .models import Coordinates, GeoGuesserLocation, Mode
from .session import GameSession


class GeoGuesser(
    LancoCog, name="GeoGuesser", description="Lancaster-themed GeoGuesser game"
):
    geoguesser_group = app_commands.Group(
        name="geoguesser", description="GeoGuesser commands"
    )

    """ Modes """
    city_mode = Mode(
        "Lancaster City",
        "🏙️",
        10000,
        (40.0382, -76.3055),
        re.compile(r"\blancaster city\b", re.IGNORECASE),
        "Lancaster City, PA",
    )
    county_mode = Mode(
        "Lancaster County",
        "🚜",
        30000,
        (40.0467, -76.1784),
        re.compile(r"\blancaster county\b", re.IGNORECASE),
        "Lancaster County, PA",
    )
    modes = [city_mode, county_mode]

    """ Constants """
    GUESS_TIME = 20  # seconds
    WARNING_TIME = floor(GUESS_TIME / 2)
    TIME_BETWEEN_ROUNDS = 10  # seconds

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        if not hasattr(self.__class__, "_active_sessions"):
            self.__class__._active_sessions = {}
        if not hasattr(self.__class__, "_sessions_starting"):
            self.__class__._sessions_starting = []
        if not hasattr(self.__class__, "_guess_semaphore"):
            self.__class__._guess_semaphore = asyncio.Semaphore(4)
        self.gmaps = googlemaps.Client(key=os.getenv("GMAPS_API_KEY"))
        self.location_utils = LocationUtils(self.gmaps)
        self.bot.database.create_tables([LocationModel, GeoguesserGameResult])

    @commands.Cog.listener()
    async def on_ready(self):
        self.__class__._active_sessions.clear()
        self.__class__._sessions_starting.clear()
        self.logger.info("GeoGuesser session state cleared on ready")

    @property
    def active_sessions(self):
        return self.__class__._active_sessions

    @property
    def sessions_starting(self):
        return self.__class__._sessions_starting

    def get_street_view_cache_path(self, location: GeoGuesserLocation) -> str:
        """Returns the path to the cached street view image"""

        cache_dir = os.path.join(self.get_cog_data_directory(), "streetview_cache")
        cached_image_path = os.path.join(cache_dir, f"{location.id}.jpg")

        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

        return cached_image_path

    async def load_locations_from_db(
        self, mode: Mode, count: int
    ) -> list[GeoGuesserLocation]:
        """Loads the locations from the database"""
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
            if not os.path.exists(cached_image_path):
                street_view_url = self.location_utils.get_street_view_url(
                    location.road_coords
                )
                async with aiohttp.ClientSession() as s:
                    async with s.get(street_view_url) as resp:
                        if resp.status == 200:
                            with open(cached_image_path, "wb") as f:
                                f.write(await resp.read())

        await asyncio.gather(*[cache_image(loc) for loc in locations])

        return locations

    def get_session(self, channel) -> GameSession:
        """Gets the active session for the given channel or channel ID."""
        channel_id = channel.id if hasattr(channel, "id") else channel
        return self.active_sessions.get(channel_id)

    async def callback(self, interaction: discord.Interaction):
        """Callback for the mode select"""
        mode_value = interaction.data["values"][0]
        mode = next((mode for mode in self.modes if mode.name == mode_value), None)
        channel = interaction.channel or self.bot.get_channel(interaction.channel_id)
        await interaction.response.defer()
        await self.initialize_session(mode, channel, interaction.user)

    def build_modes_select(self) -> Select:
        """Builds the selection prompt for the modes"""
        options = []
        for mode in self.modes:
            options.append(
                discord.SelectOption(label=mode.name, emoji=mode.icon, value=mode.name)
            )

        select = Select(placeholder="Choose a Mode", options=options)
        return select

    @geoguesser_group.command(
        name="start", description="Start a new GeoGuesser session"
    )
    async def start(self, interaction: discord.Interaction):
        """Starts a new GeoGuesser session"""
        self.logger.info(
            f"Start called — active_sessions: {list(self.active_sessions.keys())}, sessions_starting: {self.sessions_starting}, channel: {interaction.channel_id}"
        )
        if interaction.channel_id in self.active_sessions:
            await interaction.response.send_message("A session is already in progress")
            return

        if interaction.channel_id in self.sessions_starting:
            await interaction.response.send_message("A session is already starting")
            return

        self.sessions_starting.append(interaction.channel_id)

        select = self.build_modes_select()
        select.callback = self.callback

        view = View()
        view.add_item(select)

        await interaction.response.send_message(view=view)

    async def population_callback(self, interaction: discord.Interaction):
        """Callback for the population select"""
        mode_value = interaction.data["values"][0]
        mode = next((mode for mode in self.modes if mode.name == mode_value), None)

        await interaction.response.defer()

        # TODO make population count configurable
        count = 20
        self.logger.info(
            f"{interaction.user} started populating {count} locations for mode '{mode.name}'"
        )

        progress_msg = await interaction.followup.send(
            f"Generating locations for **{mode.name}**: 0 / {count}...", wait=True
        )

        try:

            def generate_and_save():
                import googlemaps
                from peewee import SqliteDatabase

                thread_db = SqliteDatabase(os.getenv("SQLITE_DB"))
                thread_db.connect()
                thread_gmaps = googlemaps.Client(key=os.getenv("GMAPS_API_KEY"))
                thread_location_utils = LocationUtils(thread_gmaps)
                LocationModel.bind(thread_db)
                try:
                    locations = thread_location_utils.get_geoguesser_locations_sync(
                        mode, count
                    )
                    with thread_db.atomic():
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

            collected = await asyncio.to_thread(generate_and_save)

            labeled_count = sum(1 for l in collected if l.label)
            total = (
                LocationModel.select().where(LocationModel.mode == mode.name).count()
            )
            self.logger.info(
                f"Populate complete for '{mode.name}': {len(collected)} added ({labeled_count} labeled), {total} total in DB"
            )
            await progress_msg.edit(
                content=f"Done! Added **{len(collected)}** locations for **{mode.name}** ({labeled_count} with labels). "
                f"Total in DB: **{total}**."
            )
        except Exception as e:
            self.logger.error(f"Populate failed for '{mode.name}': {e}", exc_info=True)
            await progress_msg.edit(content=f"Populate failed: ```{e}```")

    @geoguesser_group.command(name="wipe", description="Wipe all locations for a mode")
    @is_bot_owner()
    async def wipe(self, interaction: discord.Interaction):
        """Wipes all locations from the database for a selected mode."""
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
        name="stats", description="Show GeoGuesser database stats"
    )
    @is_bot_owner()
    async def stats(self, interaction: discord.Interaction):
        """Shows location counts per mode and total games recorded."""
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
            GeoguesserGameResult.select(GeoguesserGameResult.game_id).distinct().count()
        )
        lines.append(f"\nGames recorded: **{games}**")

        embed = discord.Embed(
            title="GeoGuesser Stats", description="\n".join(lines), color=0x316CA3
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @geoguesser_group.command(
        name="leaderboard",
        description="Show the GeoGuesser leaderboard for this server",
    )
    async def leaderboard(self, interaction: discord.Interaction, period: str = "all"):
        """Shows the guild leaderboard. period: all | today | week"""
        import datetime

        guild_id = interaction.guild.id
        query = GeoguesserGameResult.select().where(
            GeoguesserGameResult.guild_id == guild_id
        )

        now = datetime.datetime.utcnow()
        if period == "today":
            cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.where(GeoguesserGameResult.played_at >= cutoff)
            period_label = "Today"
        elif period == "week":
            cutoff = now - datetime.timedelta(days=7)
            query = query.where(GeoguesserGameResult.played_at >= cutoff)
            period_label = "This Week"
        else:
            period_label = "All Time"

        totals: dict[int, float] = {}
        for row in query:
            totals[row.user_id] = totals.get(row.user_id, 0) + row.score

        if not totals:
            await interaction.response.send_message(
                "No results recorded yet.", ephemeral=True
            )
            return

        sorted_players = sorted(totals.items(), key=lambda x: x[1], reverse=True)

        lines = []
        for user_id, score in sorted_players[:10]:
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else f"<{user_id}>"
            lines.append(f"{len(lines) + 1}. `{name}` ({score:.0f})")

        embed = discord.Embed(
            title=f"GeoGuesser Leaderboard — {period_label}", color=0x316CA3
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
        """Populates the database with locations"""
        select = self.build_modes_select()

        select.callback = self.population_callback

        view = View()
        view.add_item(select)

        await interaction.response.send_message(view=view)

    @geoguesser_group.command(
        name="stop", description="Stop the current GeoGuesser session"
    )
    async def stop(self, interaction: discord.Interaction):
        """Stops the current GeoGuesser session"""
        session = self.get_session(interaction.channel_id)
        if not session:
            await interaction.response.send_message("No session is in progress")
            return

        self.logger.info(
            f"Session stopped by {interaction.user} in #{interaction.channel} (guild: {interaction.guild}), round {session.current_round + 1}/{len(session.rounds)}"
        )
        session.cancel()
        self.active_sessions.pop(interaction.channel.id, None)
        if interaction.channel.id in self.sessions_starting:
            self.sessions_starting.remove(interaction.channel.id)

        if session.current_round_message:
            try:
                old = session.current_round_message.embeds[0]
                stopped_embed = discord.Embed(
                    title=old.title,
                    description="Session stopped.",
                    color=old.color.value,
                )
                await session.current_round_message.edit(
                    embed=stopped_embed, attachments=[]
                )
            except discord.HTTPException as e:
                self.logger.warning(f"Failed to edit round embed on stop: {e}")

        if session.round_warning_message:
            try:
                await session.round_warning_message.delete()
            except discord.HTTPException:
                pass
            session.round_warning_message = None

        await interaction.response.send_message("Session stopped")

    @geoguesser_group.command(
        name="skip", description="Skips the current GeoGuesser round"
    )
    async def skip(self, interaction: discord.Interaction):
        """Skips the current GeoGuesser round"""
        session = self.get_session(interaction.channel_id)
        if not session:
            await interaction.response.send_message("No session is in progress")
            return

        if interaction.user != session.host:
            await interaction.response.send_message(
                "Only the host can skip the round", ephemeral=True
            )
            return

        if session.round_deadline == 0.0:
            await interaction.response.send_message(
                "Guessing is not currently active — wait for the next round to start.",
                ephemeral=True,
            )
            return

        skipped_round = session.current_round + 1
        self.logger.info(
            f"Round {skipped_round}/{len(session.rounds)} skipped by {interaction.user} in #{interaction.channel}"
        )

        if session.round_task and not session.round_task.done():
            session.round_task.cancel()

        # freeze the embed and kill the warning
        session.round_deadline = 0.0
        if session.current_round_message:
            try:
                old = session.current_round_message.embeds[0]
                frozen = discord.Embed(
                    title=old.title, description=old.description, color=old.color.value
                )
                frozen.add_field(
                    name="Round",
                    value=f"{session.current_round + 1} / {len(session.rounds)}",
                    inline=True,
                )
                frozen.add_field(name="Guessing closed", value="Skipped", inline=True)
                frozen.set_image(url="attachment://streetview.jpg")
                await session.current_round_message.edit(embed=frozen)
            except discord.HTTPException as e:
                self.logger.warning(f"Failed to freeze round embed on skip: {e}")

        if session.round_warning_message:
            try:
                await session.round_warning_message.delete()
            except discord.HTTPException:
                pass
            session.round_warning_message = None

        if session.has_next_round():
            session.next()
            embed = discord.Embed(
                title=f"Round {skipped_round} skipped", color=0x316CA3
            )
            await interaction.response.send_message(embed=embed)
            asyncio.create_task(self.post_current_round(session, immediate=True))
        else:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title=f"Round {skipped_round} skipped", color=0x316CA3
                )
            )
            asyncio.create_task(self.post_final_results(session, immediate=True))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handles a guess message for the current round"""
        if message.author.bot:
            return

        session = self.get_session(message.channel)
        if not session:
            return

        now = time.time()
        if now > session.round_deadline:
            self.logger.debug(
                f"{message.author} guess ignored — deadline passed (now={now:.1f}, deadline={session.round_deadline:.1f})"
            )
            return

        r = session.get_current_round()
        if not r:
            self.logger.debug(f"{message.author} guess ignored — no current round")
            return

        if r.has_guessed(message.author.id):
            self.logger.debug(f"{message.author} already guessed this round, ignoring")
            return

        guess = message.content
        round_at_submit = session.current_round
        self.logger.info(
            f"{message.author} submitting guess '{guess}' (deadline in {session.round_deadline - now:.1f}s)"
        )
        async with self.__class__._guess_semaphore:
            result = await asyncio.to_thread(
                session.handle_guess, message.author, guess
            )

        # discard if the round changed while we were waiting on the API
        if session.current_round != round_at_submit:
            self.logger.info(
                f"{message.author} guess '{guess}' discarded — round changed during API call"
            )
            return

        if not result:
            self.logger.info(f"{message.author} guess '{guess}' could not be resolved")
            return

        await message.add_reaction("✅")

        self.logger.info(
            f"{message.author} guessed '{guess}' — {result.distance:.0f}m away, score: {result.score:.1f}"
        )

    async def initialize_session(
        self, mode: Mode, channel: discord.TextChannel, host: discord.Member
    ):
        """Initializes a new GeoGuesser session"""
        self.logger.info(
            f"Starting session in #{channel} (guild: {channel.guild}) — mode: {mode.name}, host: {host}"
        )
        try:
            session = GameSession(mode, channel, host, self.gmaps, self.location_utils)
            self.active_sessions[channel.id] = session
            locations = await self.load_locations_from_db(mode, 10)
            self.logger.info(
                f"Loaded {len(locations)} locations for session in #{channel}"
            )
            session.init(locations)
        except Exception as e:
            self.logger.error(
                f"Failed to initialize session in #{channel}: {e}", exc_info=True
            )
            self.active_sessions.pop(channel.id, None)
            await channel.send("Failed to start the session, please try again.")
            return
        finally:
            if channel.id in self.sessions_starting:
                self.sessions_starting.remove(channel.id)

        asyncio.create_task(self.post_current_round(session, True, intro=True))

    def build_leaderboard(self, session: GameSession) -> str:
        """Builds the leaderboard for the given session"""
        if len(session.members) == 0:
            return "No scores yet"

        sorted_players = sorted(
            session.members.items(), key=lambda item: item[1], reverse=True
        )

        lines = []
        for player_id, score in sorted_players:
            if score <= 0:
                continue
            player = session.channel.guild.get_member(player_id)
            lines.append(f"{len(lines) + 1}. `{player.display_name}` ({score:.0f})")
            if len(lines) >= 10:
                break

        return "\n".join(lines) if lines else "No scores yet"

    async def post_final_results(self, session: GameSession, immediate: bool = False):
        """Posts the final results of the session"""
        if session.cancelled:
            return

        # show the last round's results first (answer, map, standings)
        await self.post_round_results(session)

        if session.cancelled:
            return

        self.active_sessions.pop(session.channel.id, None)
        self.logger.info(
            f"Session ended in #{session.channel} — {len(session.members)} players, {len(session.rounds)} rounds"
        )

        # record per-player results if there were multiple players (prevent solo abuse)
        if len(session.members) > 1:
            with self.bot.database.atomic():
                for user_id, score in session.members.items():
                    GeoguesserGameResult.create(
                        game_id=session.game_id,
                        guild_id=session.channel.guild.id,
                        user_id=user_id,
                        mode=session.mode.name,
                        score=score,
                        rounds_played=len(session.rounds),
                    )
            self.logger.info(
                f"Recorded results for game {session.game_id} — {len(session.members)} players"
            )

        embed = discord.Embed(title="GeoGuesser Results", color=0x316CA3)
        embed.add_field(
            name=f"End of {len(session.rounds)} rounds", value="", inline=False
        )

        leaderboard = self.build_leaderboard(session)
        embed.add_field(name="Final Standings", value=leaderboard, inline=False)

        await session.channel.send(embed=embed)

    async def post_round_results(self, session: GameSession):
        """Posts the results of the current round"""
        if session.cancelled:
            return

        await asyncio.sleep(self.GUESS_TIME)

        if session.cancelled:
            return

        session.round_deadline = 0.0
        next_round_time = int(time.time()) + self.TIME_BETWEEN_ROUNDS

        r = session.get_current_round()
        self.logger.info(
            f"Round {r.number + 1}/{len(session.rounds)} ended in #{session.channel} — "
            f"{len(r.guesses)} guess(es), answer: {r.location.label or f'{r.location.road_coords.lat:.5f},{r.location.road_coords.lng:.5f}'}"
        )

        # freeze the round embed — rebuild without the attachment so it doesn't re-render the image
        if session.current_round_message:
            try:
                old = session.current_round_message.embeds[0]
                frozen_embed = discord.Embed(
                    title=old.title, description=old.description, color=old.color.value
                )
                frozen_embed.add_field(
                    name="Round",
                    value=f"{session.current_round + 1} / {len(session.rounds)}",
                    inline=True,
                )
                frozen_embed.add_field(
                    name="Guessing closed", value="Round ended", inline=True
                )
                frozen_embed.set_image(url="attachment://streetview.jpg")
                await session.current_round_message.edit(embed=frozen_embed)
            except discord.HTTPException as e:
                self.logger.warning(f"Failed to freeze round embed: {e}")

        # delete the warning message — it's stale too
        if session.round_warning_message:
            try:
                await session.round_warning_message.delete()
            except discord.HTTPException as e:
                self.logger.warning(f"Failed to delete warning message: {e}")
            session.round_warning_message = None
        coords = r.location.road_coords
        maps_url = f"https://www.google.com/maps?q={coords.lat},{coords.lng}"
        location_label = r.location.label or f"{coords.lat:.5f}, {coords.lng:.5f}"

        # build static map with answer marker (red star) + color-coded player markers
        marker_colors = ["blue", "green", "purple", "orange", "yellow"]
        map_params = (
            f"center={coords.lat},{coords.lng}"
            f"&zoom=16&size=600x300&maptype=roadmap"
            f"&markers=color:red%7Clabel:A%7C{coords.lat},{coords.lng}"
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

        closest_str = None
        furthest_str = None
        if sorted_guesses:
            closest_id, closest_result = sorted_guesses[0]
            closest_member = session.channel.guild.get_member(closest_id)
            closest_str = f"`{closest_member.display_name}` ({format_distance(closest_result.distance)})"
            if len(sorted_guesses) > 1:
                furthest_id, furthest_result = sorted_guesses[-1]
                furthest_member = session.channel.guild.get_member(furthest_id)
                furthest_str = f"`{furthest_member.display_name}` ({format_distance(furthest_result.distance)})"

        embed = discord.Embed(title="End of the round", color=0x316CA3)
        embed.add_field(
            name="Round", value=f"{r.number + 1} of {len(session.rounds)}", inline=True
        )
        embed.add_field(
            name="Answer", value=f"[{location_label}]({maps_url})", inline=True
        )

        if closest_str:
            embed.add_field(name="Closest", value=closest_str, inline=True)
        if furthest_str:
            embed.add_field(name="Furthest", value=furthest_str, inline=True)

        leaderboard = self.build_leaderboard(session)
        embed.add_field(name="Standings", value=leaderboard, inline=False)

        if session.has_next_round():
            embed.add_field(
                name="Next round", value=f"<t:{next_round_time}:R>", inline=False
            )

        embed.set_image(url=static_map_url)

        session.round_results_message = await session.channel.send(embed=embed)

    async def post_round_warning(self, session: GameSession):
        """Posts a warning message for the current round"""
        if session.cancelled:
            return

        deadline = int(session.round_deadline)
        await asyncio.sleep(self.WARNING_TIME)

        if session.cancelled:
            return

        session.round_warning_message = await session.channel.send(
            f"Guessing closes <t:{deadline}:R>!"
        )

    async def post_current_round(
        self, session: GameSession, immediate: bool = False, intro: bool = False
    ):
        """Posts the current round"""
        if session.cancelled:
            return

        if not immediate:
            await asyncio.sleep(self.TIME_BETWEEN_ROUNDS)

        if session.cancelled:
            return

        # remove the "Next round" countdown from the previous results embed
        if session.round_results_message:
            try:
                prev_embed = session.round_results_message.embeds[0]
                prev_embed._fields = [
                    f for f in prev_embed._fields if f["name"] != "Next round"
                ]
                await session.round_results_message.edit(embed=prev_embed)
            except discord.HTTPException:
                pass
            session.round_results_message = None

        current_round = session.get_current_round()

        if not current_round:
            return

        self.logger.info(
            f"Round {session.current_round + 1}/{len(session.rounds)} starting in #{session.channel} — "
            f"location: {current_round.location.label or f'{current_round.location.road_coords.lat:.5f},{current_round.location.road_coords.lng:.5f}'}"
        )

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

        streetview_attachment = discord.File(
            cached_image_path, filename="streetview.jpg"
        )
        session.current_round_message = await session.channel.send(
            embed=embed, file=streetview_attachment
        )

        # compute deadline after send so the timestamp is never in the past
        deadline = int(time.time()) + self.GUESS_TIME
        session.round_deadline = deadline
        session.idle = False
        embed.add_field(name="Guessing closes", value=f"<t:{deadline}:R>", inline=True)
        await session.current_round_message.edit(embed=embed)

        asyncio.create_task(self.post_round_warning(session))

        if session.has_next_round():
            session.round_task = asyncio.create_task(self._advance_round(session))
        else:
            session.round_task = asyncio.create_task(self.post_final_results(session))

    async def _advance_round(self, session: GameSession):
        """Waits for the round to end then posts results and starts the next round."""
        await self.post_round_results(session)
        if not session.cancelled:
            session.next()
            asyncio.create_task(self.post_current_round(session, False))


async def setup(bot):
    await bot.add_cog(GeoGuesser(bot))
