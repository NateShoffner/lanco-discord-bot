import datetime
from uuid import uuid4

from db import BaseModel
from peewee import *


class RoundGameResult(BaseModel):
    id = AutoField()
    game_name = CharField()
    game_id = UUIDField()
    guild_id = BigIntegerField()
    user_id = BigIntegerField()
    mode = CharField()
    score = FloatField()
    rounds_played = IntegerField()
    scoring_version = IntegerField()
    played_at = DateTimeField(default=datetime.datetime.utcnow)

    class Meta:
        table_name = "round_game_results"
        indexes = (
            (("game_name", "guild_id", "user_id"), False),
            (("game_name", "game_id"), False),
        )
