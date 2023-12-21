from math import floor
import re
import aiohttp
import asyncio
import discord
import os
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select

import googlemaps
from .models import Mode
from .session import GameSession

from cogs.lancocog import LancoCog


class GeoGuesser(LancoCog):
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

    active_sessions = {}  # channel_id: session
    sessions_starting = (
        []
    )  # TODO won't need this if we precompile the select options so there's not risk of multiple sessions starting

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot = bot
        self.gmaps = googlemaps.Client(key=os.getenv("GMAPS_API_KEY"))

    def get_session(self, channel: discord.TextChannel) -> GameSession:
        """Gets the active session for the given channel"""
        return self.active_sessions.get(channel.id)

    async def callback(self, interaction: discord.Interaction):
        """Callback for the mode select"""
        mode_value = interaction.data["values"][0]
        mode = next((mode for mode in self.modes if mode.name == mode_value), None)
        await interaction.channel.typing()
        await interaction.response.defer()
        await self.initialize_session(mode, interaction.channel, interaction.user)

    @geoguesser_group.command(
        name="start", description="Start a new GeoGuesser session"
    )
    async def start(self, interaction: discord.Interaction):
        """Starts a new GeoGuesser session"""
        if interaction.channel.id in self.active_sessions:
            await interaction.response.send_message("A session is already in progress")
            return

        if interaction.channel.id in self.sessions_starting:
            await interaction.response.send_message("A session is already starting")
            return

        self.sessions_starting.append(interaction.channel.id)

        options = []
        for mode in self.modes:
            options.append(
                discord.SelectOption(label=mode.name, emoji=mode.icon, value=mode.name)
            )

        select = Select(placeholder="Choose a Mode", options=options)
        select.callback = self.callback

        view = View()
        view.add_item(select)

        await interaction.channel.typing()
        await interaction.response.send_message(view=view)

    @geoguesser_group.command(
        name="stop", description="Stop the current GeoGuesser session"
    )
    async def stop(self, interaction: discord.Interaction):
        """Stops the current GeoGuesser session"""
        session = self.get_session(interaction.channel)
        if not session:
            await interaction.response.send_message("No session is in progress")
            return

        await interaction.channel.typing()
        self.active_sessions.pop(interaction.channel.id)
        await interaction.response.send_message("Session stopped")

    @geoguesser_group.command(
        name="skip", description="Skips the current GeoGuesser round"
    )
    async def skip(self, interaction: discord.Interaction):
        """Skips the current GeoGuesser round"""
        session = self.get_session(interaction.channel)
        if not session:
            await interaction.response.send_message("No session is in progress")
            return

        await interaction.channel.typing()

        if interaction.user != session.host:
            await interaction.response.send_message(
                "Only the host can skip the round", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"Round {session.current_round + 1} skipped"
        )

        if session.has_next_round():
            session.next()
            await self.post_current_round(session)
        else:
            await self.post_final_results(session)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handles a guess message for the current round"""
        if message.author.bot:
            return

        session = self.get_session(message.channel)
        if not session:
            return

        if session.is_idle():
            return

        r = session.get_current_round()
        if not r:
            return

        if r.has_guessed(message.author.id):
            self.logger.info(f"{message.author.display_name} has already guessed")
            return

        guess = message.content
        result = session.handle_guess(message.author, guess)

        if not result:
            await message.channel.send(
                f"{message.author.mention} your guess was invalid, please try again"
            )
            return

        """
        await message.channel.send(
            f"{message.author.mention} your guess was **{result.distance:2f}** meters away from the actual location"
        )"""

        self.logger.info(
            f"{message.author.display_name} guessed {guess} and got {result.score:.2f} points"
        )

    async def initialize_session(
        self, mode: Mode, channel: discord.TextChannel, host: discord.Member
    ):
        """Initializes a new GeoGuesser session"""
        session = GameSession(
            mode,
            channel,
            host,
            self.gmaps,
        )

        self.sessions_starting.remove(channel.id)
        self.active_sessions[channel.id] = session
        await session.init()

        rules = [
            f"Try to guess the location of the photo, the closer you are the more points you get",
            "You only have **one** guess per round",
            f"You have **{self.GUESS_TIME} seconds** to guess the location of the photo",
            f"Your score is based on how close your guess is to the actual location",
            f"There are **{len(session.rounds)}** rounds in this game",
            "The host of the game can can skip the round by using the `/geoguesser skip` command",
        ]

        description = f"**Mode:** {mode.icon} {mode.name}\n\n"
        description += "**Rules:**\n"
        description += "\n".join([f"- {rule}" for rule in rules])

        await channel.send(
            embed=discord.Embed(
                title=f"{host.display_name} has started a new GeoGuesser session!",
                description=description,
                color=0x316CA3,
            ),
        )

        asyncio.create_task(self.post_current_round(session, True))

    def build_leaderboard(self, session: GameSession) -> str:
        """Builds the leaderboard for the given session"""
        if len(session.members) == 0:
            return "No players lmao"

        sorted_players = sorted(
            session.members.items(), key=lambda item: item[1], reverse=True
        )

        leaderboard = ""
        count = 0
        for player_id, score in sorted_players:
            player = session.channel.guild.get_member(player_id)
            if score > 0:
                leaderboard += f"{count + 1}: `{player.display_name}` ({score:.2f})\n"
                count += 1

            if count >= 10:
                break
        leaderboard += ""

        return leaderboard

    async def post_final_results(self, session: GameSession, immediate: bool = False):
        """Posts the final results of the session"""
        if not immediate:
            await asyncio.sleep(self.GUESS_TIME)

        self.active_sessions.pop(session.channel.id)

        embed = discord.Embed(
            title=f"Final Results",
            description=f"Here are the final results from the game",
            color=0x316CA3,
        )
        leaderboard = self.build_leaderboard(session)
        embed.add_field(name="Scores", value=leaderboard, inline=False)

        await session.channel.send(embed=embed)

    async def post_round_results(self, session: GameSession):
        """Posts the results of the current round"""
        await asyncio.sleep(self.GUESS_TIME)
        session.set_idle(True)

        description = ""

        r = session.get_current_round()
        top_guessers = r.get_top_guessers()

        if len(top_guessers) > 0:
            description = "**Top Guesser(s)**\n"
            for g in top_guessers:
                description += f"**{session.channel.guild.get_member(g).display_name}** with a score of **{r.guesses[g].score:.2f}**\n"

        if session.has_next_round():
            description += (
                f"\nNext round starts in **{self.TIME_BETWEEN_ROUNDS}** seconds"
            )

        embed = discord.Embed(
            title=f"Round {r.number + 1} Results",
            description=description,
            color=0x316CA3,
        )
        leaderboard = self.build_leaderboard(session)
        embed.add_field(name="Scores", value=leaderboard, inline=False)

        await session.channel.send(embed=embed)

    async def post_round_warning(self, session: GameSession):
        """Posts a warning message for the current round"""
        await asyncio.sleep(self.WARNING_TIME)

        await session.channel.send(
            f"**{self.WARNING_TIME}** seconds left to guess the location!"
        )

    async def post_current_round(self, session: GameSession, immediate: bool = False):
        """Posts the current round"""
        if not immediate:
            await asyncio.sleep(self.TIME_BETWEEN_ROUNDS)

        current_round = session.get_current_round()

        if not current_round:
            return

        cache_dir = os.path.join(self.get_cog_data_directory(), "streetview_cache")
        road_coords_str = f"{current_round.location.road_coords.lat},{current_round.location.road_coords.lng}"
        cached_image_path = os.path.join(cache_dir, f"{road_coords_str}.jpg")

        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

        if not os.path.exists(cached_image_path):
            async with aiohttp.ClientSession() as s:
                async with s.get(current_round.location.street_view) as resp:
                    if resp.status == 200:
                        with open(cached_image_path, "wb") as f:
                            f.write(await resp.read())

        embed = discord.Embed(
            title=f"Round {session.current_round + 1}",
            description=f"You have **{self.GUESS_TIME}** seconds to guess the location of the photo below",
        )
        streetview_attachment = discord.File(
            cached_image_path, filename="streetview.jpg"
        )
        # print(current_round.location.street_view)
        embed.set_image(url="attachment://streetview.jpg")
        await session.channel.send(embed=embed, file=streetview_attachment)

        session.set_idle(False)

        asyncio.create_task(self.post_round_warning(session))

        if session.has_next_round():
            await self.post_round_results(session)
            session.next()
            asyncio.create_task(self.post_current_round(session, False))
        else:
            asyncio.create_task(self.post_final_results(session))


async def setup(bot):
    await bot.add_cog(GeoGuesser(bot))
