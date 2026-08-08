import datetime
from uuid import uuid4

from tortoise import fields
from tortoise.models import Model

SCORING_VERSION = 4
# Version history:
# 1 - haversine distance, 0 pts at 1km (too aggressive)
# 2 - haversine distance, 0 pts at mode radius (city=10km, county=30km)
# 3 - distance score (0-100) + time bonus (0-20) based on time remaining
# 4 - separate score_radius from generation radius (city=2km, county=20km)


class GeoguesserLocation(Model):
    id = fields.UUIDField(primary_key=True, default=uuid4)
    mode = fields.CharField(max_length=255)
    initial_lat = fields.FloatField()
    initial_lng = fields.FloatField()
    road_lat = fields.FloatField()
    road_lng = fields.FloatField()
    label = fields.CharField(max_length=255, null=True)

    class Meta:
        table = "geoguesser_locations"


class GeoguesserGameResult(Model):
    id = fields.IntField(primary_key=True)
    game_id = fields.UUIDField()
    guild_id = fields.BigIntField()
    user_id = fields.BigIntField()
    # TEXT in the live table rather than VARCHAR; both are TEXT affinity in
    # SQLite, and max_length only constrains the ORM side.
    mode = fields.CharField(max_length=255)
    score = fields.FloatField()
    rounds_played = fields.IntField()
    scoring_version = fields.IntField(default=SCORING_VERSION)
    played_at = fields.DatetimeField(default=datetime.datetime.utcnow)

    class Meta:
        table = "geoguesser_game_results"
