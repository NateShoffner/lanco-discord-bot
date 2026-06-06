import asyncio
import datetime
import logging
import math
import threading
import uuid

import discord
import googlemaps

from .locationutils import LocationUtils
from .models import Coordinates, GeoGuesserLocation, GuessResult, Mode, Round


class GameSession:
    """A game session"""

    def __init__(
        self,
        mode: Mode,
        channel: discord.TextChannel,
        host: discord.Member,
        gmaps: googlemaps.Client,
        location_utils: LocationUtils,
    ):
        self.mode = mode
        self.channel = channel
        self.host = host
        self.gmaps = gmaps
        self.location_utils = location_utils
        self.rounds = []
        self.members = {}  # {user_id: score}
        self.current_round = 0
        self.logger = logging.getLogger(__name__)
        self.idle = False
        self.cancelled = False
        self.round_deadline: float = 0.0
        self.game_id = uuid.uuid4()
        self._guess_lock = threading.Lock()
        self.current_round_message: discord.Message | None = None
        self.round_warning_message: discord.Message | None = None
        self.round_results_message: discord.Message | None = None
        self.round_task: asyncio.Task | None = None

    def init(self, locations: list[GeoGuesserLocation]):
        """Loads the locations for the game session"""
        for _, location in enumerate(locations):
            r = Round(_, location)
            self.rounds.append(r)
        self.start_time = datetime.datetime.now()

    def has_next_round(self) -> bool:
        """Returns whether or not there is another round"""
        if self.cancelled:
            return False
        return self.current_round < (len(self.rounds) - 1)

    def next(self):
        """Increments the next round"""
        if self.current_round >= len(self.rounds):
            return None
        self.current_round += 1
        return self.current_round

    def cancel(self):
        """Cancels the game session"""
        self.cancelled = True

    def set_idle(self, idle: bool):
        """Sets the idle state of the game session"""
        self.idle = idle

    def is_idle(self) -> bool:
        """Returns whether or not the game session is idle"""
        return self.idle

    def get_current_round(self) -> Round:
        """Returns the current round"""
        if self.current_round >= len(self.rounds):
            return None
        return self.rounds[self.current_round]

    @staticmethod
    def _haversine_meters(a: Coordinates, b: Coordinates) -> float:
        R = 6_371_000
        lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
        dlat = math.radians(b.lat - a.lat)
        dlng = math.radians(b.lng - a.lng)
        h = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        )
        return R * 2 * math.asin(math.sqrt(h))

    def handle_guess(self, member: discord.Member, guess: str) -> GuessResult:
        """Handles a guess from a member and returns the result"""
        if not self.members.get(member.id):
            self.members[member.id] = 0

        r = self.get_current_round()
        if not r:
            self.logger.warning("handle_guess called with no current round")
            return None

        guess = self.mode.get_qualified_guess(guess)
        self.logger.info(f"Qualified guess: '{guess}'")
        guess_location = self.location_utils.get_coordinates_from_location(guess)
        self.logger.info(
            f"Guess resolved to: {guess_location} (actual: {r.location.road_coords})"
        )
        if not guess_location:
            self.logger.debug(f"Could not resolve guess to coordinates: {guess}")
            return None

        # TODO this is what the city mode returns as a false positive because it centers the coords thanks to the qualifier
        false_pos_coords = Coordinates(40.0378755, -76.3055144)
        if guess_location == false_pos_coords:
            self.logger.debug(f"False positive coordinates for guess: {guess}")
            return None

        meters = self._haversine_meters(r.location.road_coords, guess_location)
        # scale scoring to the mode's radius so county guesses aren't immediately zeroed
        score_radius = self.mode.score_radius  # city=2000m, county=20000m
        distance_score = max(0, 1 - meters / score_radius) * 100

        # time bonus: up to 20 extra points for guessing early
        import time as _time

        time_remaining = max(0.0, self.round_deadline - _time.time())
        time_bonus = min(time_remaining, 20.0)  # 1pt per second remaining, max 20

        score = round(distance_score + time_bonus, 1)

        result = GuessResult(meters, score, guess_coords=guess_location)
        with self._guess_lock:
            if r.has_guessed(member.id):
                return None  # another thread beat us to it
            r.add_guess(member.id, result)
            self.members[member.id] += score

        return result
