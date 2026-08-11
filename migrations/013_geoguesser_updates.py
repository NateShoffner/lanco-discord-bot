"""Label geoguesser locations and record per-game results."""

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


class GeoguesserGameResult(Model):
    id = AutoField()
    game_id = UUIDField()
    guild_id = BigIntegerField()
    user_id = BigIntegerField()
    mode = CharField()
    score = FloatField()
    rounds_played = IntegerField()
    played_at = DateTimeField()

    class Meta:
        table_name = "geoguesser_game_results"


def upgrade(ctx: MigrationContext) -> None:
    ctx.add_columns("geoguesser_locations", label=CharField(null=True))

    ctx.create_table(GeoguesserGameResult)
    ctx.create_index("geoguesser_game_results", "idx_ggr_guild", ["guild_id"])
    ctx.create_index("geoguesser_game_results", "idx_ggr_user", ["guild_id", "user_id"])
    ctx.create_index("geoguesser_game_results", "idx_ggr_played_at", ["played_at"])

    ctx.add_columns("geoguesser_game_results", scoring_version=IntegerField(default=1))
