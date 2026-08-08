import datetime

from tortoise import fields
from tortoise.models import Model


class RoundGameResult(Model):
    id = fields.IntField(primary_key=True)
    # TEXT in the live table rather than VARCHAR; both are TEXT affinity in
    # SQLite, and max_length only constrains the ORM side.
    game_name = fields.CharField(max_length=255)
    game_id = fields.UUIDField()
    guild_id = fields.BigIntField()
    user_id = fields.BigIntField()
    mode = fields.CharField(max_length=255)
    score = fields.FloatField()
    rounds_played = fields.IntField()
    scoring_version = fields.IntField()
    played_at = fields.DatetimeField(default=datetime.datetime.utcnow)

    class Meta:
        table = "round_game_results"
        # Peewee's Meta.indexes used (columns, unique) tuples; both of these had
        # unique=False, so they map to Tortoise's plain `indexes` rather than
        # `unique_together`.
        indexes = (
            ("game_name", "guild_id", "user_id"),
            ("game_name", "game_id"),
        )
