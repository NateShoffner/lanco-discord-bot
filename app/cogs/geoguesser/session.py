import datetime
import logging
from math import cos, sin
import os
import random
from urllib.parse import urlencode
import aiohttp
import discord
import googlemaps

from .models import Coordinates, GeoGuesserLocation, GuessResult, Mode, Round


class GameSession:
    """A game session"""

    def __init__(
        self,
        mode: Mode,
        channel: discord.TextChannel,
        host: discord.Member,
        gmaps: googlemaps.Client,
    ):
        self.mode = mode
        self.channel = channel
        self.host = host
        self.gmaps = gmaps
        self.rounds = []
        self.members = {}  # {user_id: score}
        self.current_round = 0
        self.logger = logging.getLogger(__name__)
        self.idle = False

    async def init(self, num_rounds: int = 5):
        """Initializes the game session"""
        for _ in range(num_rounds):
            location = await self.get_geoguesser_location()
            # print(location)
            r = Round(_, location)
            self.rounds.append(r)

        self.start_time = datetime.datetime.now()

    def has_next_round(self) -> bool:
        """Returns whether or not there is another round"""
        return self.current_round < (len(self.rounds) - 1)

    def next(self):
        """Increments the next round"""
        if self.current_round >= len(self.rounds):
            return None
        self.current_round += 1
        return self.current_round

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
        guess_location = self.get_coordinates_from_location(guess)
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

    async def get_random_streetview_image(self, coords: Coordinates) -> str:
        """Returns a street view image URL for the given coordinates"""
        base_url = "https://maps.googleapis.com/maps/api/streetview?"
        params = {
            "location": f"{coords.lat},{coords.lng}",
            "size": "800x600",
            "fov": "120",
            "heading": "random",  # Set the heading to 'random' for a random direction
            "pitch": "0",  # Set the pitch to '0' for a horizontal view
            "key": os.getenv("GMAPS_API_KEY"),
        }

        full_url = base_url + urlencode(params)

        async with aiohttp.ClientSession() as session:
            async with session.get(full_url) as resp:
                if resp.status == 200:
                    # print(resp.url)
                    return resp.url
                else:
                    self.logger.error(f"Error: {resp.status}")
                    return None

    def get_coordinates_from_location(self, location_name: str) -> Coordinates:
        """Returns the coordinates of the location"""
        # TODO cache location names to avoid unnecessary API calls
        geocode_result = self.gmaps.geocode(location_name)
        if len(geocode_result) > 0:
            lat = geocode_result[0]["geometry"]["location"]["lat"]
            lng = geocode_result[0]["geometry"]["location"]["lng"]
            return Coordinates(lat, lng)
        else:
            self.logger.error(f"Error: {location_name} not found")
            return None

    def get_random_subcoordinate_from_bounds(bounding_box: tuple) -> tuple:
        """Returns a random coordinate within the bounding box"""
        min_lat, max_lat, min_lng, max_lng = bounding_box
        random_lat = random.uniform(min_lat, max_lat)
        random_lng = random.uniform(min_lng, max_lng)
        return random_lat, random_lng

    def get_random_subcoordinate_from_center(
        self, center_coord: tuple[float, float], radius_in_meters: int, num_points=1
    ) -> list:
        """Generates random coordinates within a given radius from a center point"""
        random_coordinates = []

        for _ in range(num_points):
            # Generate a random angle in radians
            angle = random.uniform(0, 2 * 3.141592653589793)

            # Generate a random distance within the radius
            random_distance = random.uniform(0, radius_in_meters)

            # Calculate the new coordinates
            dx = random_distance * (radius_in_meters / 111320.0) * cos(angle)
            dy = random_distance * (radius_in_meters / 111320.0) * sin(angle)

            new_latitude = center_coord[0] + (dy / 111320.0)
            new_longitude = center_coord[1] + (dx / (111320.0 * cos(center_coord[0])))

            random_coordinates.append((new_latitude, new_longitude))

        return random_coordinates

    async def get_geoguesser_location(self) -> GeoGuesserLocation:
        """Returns a geoguesser location within the bounding box"""
        road = None
        while not road:
            initial_location = self.get_random_subcoordinate_from_center(
                self.mode.center, self.mode.radius, 1
            )[0]
            # print(initial_location)
            roads = self.gmaps.snap_to_roads(initial_location)
            if len(roads) > 0:
                road = roads[0]
            else:
                print("Error: No roads found, trying again...")

        road_coords = Coordinates(
            road["location"]["latitude"], road["location"]["longitude"]
        )

        street_view = None

        street_view = await self.get_random_streetview_image(road_coords)
        if not street_view:
            self.logger.error(
                f"Error: Street view not found for {road_coords}, trying again..."
            )
            return await self.get_geoguesser_location()

        return GeoGuesserLocation(initial_location, road_coords, street_view)
