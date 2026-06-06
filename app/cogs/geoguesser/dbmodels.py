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


SCORING_VERSION = 4
# Version history:
# 1 - haversine distance, 0 pts at 1km (too aggressive)
# 2 - haversine distance, 0 pts at mode radius (city=10km, county=30km)
# 3 - distance score (0-100) + time bonus (0-20) based on time remaining
# 4 - separate score_radius from generation radius (city=2km, county=20km)


class GeoguesserGameResult(BaseModel):
    id = AutoField()
    game_id = UUIDField()
    guild_id = BigIntegerField()
    user_id = BigIntegerField()
    mode = CharField()
    score = FloatField()
    rounds_played = IntegerField()
    scoring_version = IntegerField(default=SCORING_VERSION)
    played_at = DateTimeField(default=datetime.datetime.utcnow)

    class Meta:
        table_name = "geoguesser_game_results"
