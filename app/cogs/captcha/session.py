import time

import discord
from utils.roundgame.session import RoundGameSession

from .models import CaptchaGuessResult, CaptchaMode, CaptchaRound

PLACE_SCORES = [100, 75, 50, 25]
MAX_TIME_BONUS = 20


class CaptchaSession(RoundGameSession[CaptchaRound, CaptchaGuessResult]):
    def __init__(
        self,
        mode: CaptchaMode,
        channel: discord.TextChannel,
        host: discord.Member,
        guess_time: int,
    ):
        super().__init__(channel, host)
        self.mode = mode
        self.guess_time = guess_time

    def has_guessed(self, user_id: int) -> bool:
        r = self.get_current_round()
        return r is not None and r.has_guessed(user_id)

    def handle_guess(
        self, member: discord.Member, guess: str
    ) -> CaptchaGuessResult | None:
        r = self.get_current_round()
        if not r:
            self.logger.warning("handle_guess called with no current round")
            return None

        normalized_guess = guess.strip().upper()
        correct = normalized_guess == r.challenge.answer.upper()

        with self._guess_lock:
            if r.has_guessed(member.id):
                return None

            place = r.correct_count() + 1 if correct else 0

            if correct:
                base_score = PLACE_SCORES[min(place - 1, len(PLACE_SCORES) - 1)]
                time_remaining = max(0.0, self.round_deadline - time.time())
                time_bonus = round(
                    min(time_remaining / self.guess_time, 1.0) * MAX_TIME_BONUS, 1
                )
                score = base_score + time_bonus
            else:
                score = 0.0

            result = CaptchaGuessResult(correct=correct, score=score, place=place)
            r.guesses[member.id] = result
            if correct:
                self.add_score(member.id, score)

        return result
