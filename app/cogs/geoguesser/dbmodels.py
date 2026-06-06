import datetime
from uuid import uuid4

from db import BaseModel
from peewee import *


class GeoguesserLocation(BaseModel):
    id = UUIDField(primary_key=True, default=uuid4)
    mode = CharField()
    initial_lat = FloatField()
    initial_lng = FloatField()
    road_lat = FloatField()
    road_lng = FloatField()
    label = CharField(null=True)

    class Meta:
        table_name = "geoguesser_locations"


class GeoguesserGameResult(BaseModel):
    id = AutoField()
    game_id = UUIDField()
    guild_id = BigIntegerField()
    user_id = BigIntegerField()
    mode = CharField()
    score = FloatField()
    rounds_played = IntegerField()
    played_at = DateTimeField(default=datetime.datetime.utcnow)

    class Meta:
        table_name = "geoguesser_game_results"
