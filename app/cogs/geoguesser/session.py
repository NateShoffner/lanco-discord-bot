import datetime
import logging

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

    def handle_guess(self, member: discord.Member, guess: str) -> GuessResult:
        """Handles a guess from a member and returns the result"""
        if not self.members.get(member.id):
            self.members[member.id] = 0

        r = self.get_current_round()
        if not r:
            self.logger.info("No current round")
            return None

        guess = self.mode.get_qualified_guess(guess)
        self.logger.info(f"Guess: {guess}")
        guess_location = self.location_utils.get_coordinates_from_location(guess)
        self.logger.info(f"Guess location: {guess_location}")
        if not guess_location:
            self.logger.info("Guess location not found")
            return None

        # TODO this is what the city mode returns as a false positive because it centers the coords thanks to the qualifier
        false_pos_coords = Coordinates(40.0378755, -76.3055144)
        if guess_location == false_pos_coords:
            self.logger.info("False positive, returning")
            return None

        # calculate the distance between the actual location and the guessed location (for simplicity, using Euclidean distance)
        distance = (
            (guess_location.lat - r.location.road_coords.lat) ** 2
            + (guess_location.lng - r.location.road_coords.lng) ** 2
        ) ** 0.5
        score = (
            max(0, 1 - distance / 0.02) * 100
        )  # max score is 100, reduce score based on distance

        matrix = self.gmaps.distance_matrix(
            r.location.road_coords.to_tuple(), guess_location.to_tuple()
        )
        matrix_elements = matrix["rows"][0]["elements"][0]

        if matrix_elements["status"] == "ZERO_RESULTS":
            self.logger.info("Error: Distance matrix returned no results")
            return None

        meters = matrix_elements["distance"]["value"]
        """
        print(f"Difference in meters: {meters}")
        print(f"Your guess: {guess_location}")
        print(f"Actual location: {r.location.road_coords}")
        print(f"Distance: {distance:.5f} degrees")
        print(f"Score: {score:.2f}")
        """

        result = GuessResult(meters, score)
        r.add_guess(member.id, result)
        self.members[member.id] += score

        return result
