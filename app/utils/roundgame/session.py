import asyncio
import datetime
import logging
import threading
import uuid
from typing import Generic, TypeVar

import discord

TRound = TypeVar("TRound")
TResult = TypeVar("TResult")


class RoundGameSession(Generic[TRound, TResult]):
    def __init__(self, channel: discord.TextChannel, host: discord.Member):
        self.channel = channel
        self.host = host
        self.rounds: list[TRound] = []
        self.members: dict[int, float] = {}
        self.current_round: int = 0
        self.logger = logging.getLogger(__name__)
        self.cancelled: bool = False
        self.round_deadline: float = 0.0
        self.game_id: uuid.UUID = uuid.uuid4()
        self.start_time: datetime.datetime | None = None
        self._guess_lock = threading.Lock()
        self.current_round_message: discord.Message | None = None
        self.round_warning_message: discord.Message | None = None
        self.round_results_message: discord.Message | None = None
        self.round_task: asyncio.Task | None = None
        self.warning_task: asyncio.Task | None = None
        self.skip_message: discord.Message | None = None

    def init(self, rounds: list[TRound]):
        self.rounds = rounds
        self.start_time = datetime.datetime.now()

    def has_next_round(self) -> bool:
        if self.cancelled:
            return False
        return self.current_round < (len(self.rounds) - 1)

    def next(self):
        if self.current_round >= len(self.rounds):
            return None
        self.current_round += 1
        return self.current_round

    def cancel(self):
        self.cancelled = True

    def get_current_round(self) -> TRound | None:
        if self.current_round >= len(self.rounds):
            return None
        return self.rounds[self.current_round]

    def has_guessed(self, user_id: int) -> bool:
        raise NotImplementedError

    def add_score(self, user_id: int, score: float):
        self.members[user_id] = self.members.get(user_id, 0) + score

    def handle_guess(self, member: discord.Member, guess: str) -> TResult | None:
        raise NotImplementedError
