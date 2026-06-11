import random
import string
from dataclasses import dataclass, field
from io import BytesIO


@dataclass
class CaptchaChallenge:
    answer: str
    image_bytes: bytes


@dataclass
class CaptchaGuessResult:
    correct: bool
    score: float
    place: int  # 1-based rank among correct guessers this round


@dataclass
class CaptchaRound:
    number: int
    challenge: CaptchaChallenge
    # {user_id: CaptchaGuessResult} — insertion order = answer order
    guesses: dict = field(default_factory=dict)

    def has_guessed(self, user_id: int) -> bool:
        return user_id in self.guesses

    def correct_count(self) -> int:
        return sum(1 for r in self.guesses.values() if r.correct)


class CaptchaMode:
    def __init__(self, name: str, icon: str, description: str):
        self.name = name
        self.icon = icon
        self.description = description

    def generate_answer(self) -> str:
        raise NotImplementedError


class AlphanumericMode(CaptchaMode):
    def __init__(self):
        super().__init__("Alphanumeric", "🔢", "Random 5-character codes (e.g. HJ7K2)")

    def generate_answer(self) -> str:
        chars = string.ascii_uppercase + string.digits
        return "".join(random.choices(chars, k=5))


class DictionaryMode(CaptchaMode):
    WORDS = [
        "apple",
        "brave",
        "chair",
        "dance",
        "eagle",
        "flame",
        "grace",
        "heart",
        "ivory",
        "joker",
        "kneel",
        "lemon",
        "mango",
        "noble",
        "ocean",
        "piano",
        "queen",
        "ridge",
        "storm",
        "table",
        "ultra",
        "vapor",
        "witch",
        "xenon",
        "yacht",
        "zebra",
        "anchor",
        "blaze",
        "crisp",
        "dusty",
        "ember",
        "frost",
        "glide",
        "hippo",
        "inlet",
        "jelly",
        "knack",
        "lunar",
        "maple",
        "ninja",
        "otter",
        "pixel",
        "quirk",
        "raven",
        "salsa",
        "tiger",
        "umbra",
        "vivid",
        "waltz",
        "xerox",
        "yield",
        "zonal",
    ]

    def __init__(self):
        super().__init__("Dictionary", "📖", "Common English words")

    def generate_answer(self) -> str:
        return random.choice(self.WORDS).upper()


class LancasterMode(CaptchaMode):
    WORDS = [
        "LITITZ",
        "EPHRATA",
        "MANHEIM",
        "STRASBURG",
        "INTERCOURSE",
        "BIRD IN HAND",
        "PARADISE",
        "GORDONVILLE",
        "RONKS",
        "LEOLA",
        "QUARRYVILLE",
        "ELIZABETHTOWN",
        "MOUNT JOY",
        "MARIETTA",
        "COLUMBIA",
        "MILLERSVILLE",
        "WILLOW STREET",
        "CONESTOGA",
        "DRUMORE",
        "KIRKWOOD",
        "TERRE HILL",
        "HOLTWOOD",
        "RAWLINSVILLE",
        "BRICKERVILLE",
        "NARVON",
        "BLUE BALL",
        "GOODVILLE",
        "NEW HOLLAND",
        "REINHOLDS",
        "BROWNSTOWN",
        "SMOKETOWN",
        "RONKS",
        "GAP",
        "KINZERS",
        "CHRISTIANA",
        "LAMPETER",
        "BAUSMAN",
        "LANDISVILLE",
        "SALUNGA",
        "ROHRERSTOWN",
        "EAST PETERSBURG",
        "MOUNTVILLE",
        "WASHINGTON BORO",
        "CONOY",
        "PENN MANOR",
        "HEMPFIELD",
        "MANHEIM TOWNSHIP",
    ]

    def __init__(self):
        super().__init__("Lancaster", "🌾", "Lancaster County places and neighborhoods")

    def generate_answer(self) -> str:
        return random.choice(self.WORDS)
