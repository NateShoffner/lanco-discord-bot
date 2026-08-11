"""Add the shared results table used by all round based games."""

from peewee import (
    AutoField,
    BigIntegerField,
    CharField,
    DateTimeField,
    FloatField,
    IntegerField,
    Model,
    UUIDField,
)

from migrations.helpers import MigrationContext


class RoundGameResult(Model):
    id = AutoField()
    game_name = CharField()
    game_id = UUIDField()
    guild_id = BigIntegerField()
    user_id = BigIntegerField()
    mode = CharField()
    score = FloatField()
    rounds_played = IntegerField()
    scoring_version = IntegerField()
    played_at = DateTimeField()

    class Meta:
        table_name = "round_game_results"


def upgrade(ctx: MigrationContext) -> None:
    ctx.create_table(RoundGameResult)
    ctx.create_index(
        "round_game_results",
        "idx_rgr_game_guild_user",
        ["game_name", "guild_id", "user_id"],
    )
    ctx.create_index("round_game_results", "idx_rgr_game_id", ["game_name", "game_id"])
