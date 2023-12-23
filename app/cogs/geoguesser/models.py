from dataclasses import dataclass
import re
from typing import Optional
import uuid


@dataclass
class Coordinates:
    """A pair of latitude and longitude coordinates"""

    lat: float
    """ The latitude of the coordinates """
    lng: float
    """ The longitude of the coordinates """

    def to_tuple(self) -> tuple[float, float]:
        return (self.lat, self.lng)


@dataclass
class GuessResult:
    """The result of a guess"""

    distance: float
    """ The distance between the guess and the actual location"""

    score: float
    """ The score of the guess """


@dataclass
class GeoGuesserLocation:
    """A GeoGuesser location"""

    initial_location: Coordinates
    """ The initial coordinates of the location before road snapping """
    road_coords: Coordinates
    """ The coordinates of the snapped road """

    id: Optional[uuid.UUID] = None
    """ The ID of the location """


class Mode:
    """Game mode definition"""

    def __init__(
        self,
        name: str,
        icon: str,
        radius: int,
        center: tuple[float, float],
        qualifier_pattern: re.Pattern,
        qualifier_replacement: str,
    ):
        self.name = name
        self.icon = icon
        self.radius = radius
        self.center = center
        self.qualifier_pattern = qualifier_pattern
        self.qualifier_replacement = qualifier_replacement

    def get_qualified_guess(self, guess: str) -> str:
        """Returns a qualified guess if the guess does not match the qualifier pattern"""
        if not self.qualifier_pattern:
            return guess
        if not re.search(self.qualifier_pattern, guess):
            return guess + " " + self.qualifier_replacement
        else:
            return guess


class Round:
    """A round of GeoGuesser"""

    def __init__(self, number: int, location: GeoGuesserLocation):
        self.number = number
        self.location = location
        self.guesses = {}  # {user_id: GuessResult}

    def add_guess(self, user_id: int, guess_result: GuessResult):
        """Adds a users' guess to the round"""
        self.guesses[user_id] = guess_result

    def has_guessed(self, user_id: int) -> bool:
        """Returns whether or not a user has guessed"""
        return user_id in self.guesses

    def get_top_guessers(self) -> [int]:
        """Returns the user_id's of the top guessers"""
        top_guessers = []

        if len(self.guesses) == 0:
            return top_guessers

        sorted_guesses = sorted(
            self.guesses.items(), key=lambda x: x[1].score, reverse=True
        )

        # see if there is are any ties
        top_score = sorted_guesses[0][1].score

        for guess in sorted_guesses:
            if guess[1].score == top_score:
                top_guessers.append(guess[0])
            else:
                break

        return top_guessers
