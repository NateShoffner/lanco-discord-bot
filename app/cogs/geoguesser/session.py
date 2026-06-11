import asyncio
import math
import time

import discord
import googlemaps
from utils.roundgame.session import RoundGameSession

from .locationutils import LocationUtils
from .models import Coordinates, GeoGuesserLocation, GuessResult, Mode, Round


class GameSession(RoundGameSession[Round, GuessResult]):
    def __init__(
        self,
        mode: Mode,
        channel: discord.TextChannel,
        host: discord.Member,
        gmaps: googlemaps.Client,
        location_utils: LocationUtils,
    ):
        super().__init__(channel, host)
        self.mode = mode
        self.gmaps = gmaps
        self.location_utils = location_utils

    def has_guessed(self, user_id: int) -> bool:
        r = self.get_current_round()
        return r is not None and r.has_guessed(user_id)

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

    def handle_guess(self, member: discord.Member, guess: str) -> GuessResult | None:
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

        # false positive: city mode returns center coords for unresolvable guesses
        false_pos_coords = Coordinates(40.0378755, -76.3055144)
        if guess_location == false_pos_coords:
            self.logger.debug(f"False positive coordinates for guess: {guess}")
            return None

        meters = self._haversine_meters(r.location.road_coords, guess_location)
        score_radius = self.mode.score_radius
        distance_score = max(0, 1 - meters / score_radius) * 100

        time_remaining = max(0.0, self.round_deadline - time.time())
        time_bonus = min(time_remaining, 20.0)
        score = round(distance_score + time_bonus, 1)

        result = GuessResult(meters, score, guess_coords=guess_location)
        with self._guess_lock:
            if r.has_guessed(member.id):
                return None
            r.add_guess(member.id, result)
            self.add_score(member.id, score)

        return result
