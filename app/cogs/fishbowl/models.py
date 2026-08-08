from tortoise import fields
from tortoise.models import Model


class FishbowlConfig(Model):
    id = fields.IntField(primary_key=True)
    channel_id = fields.IntField()
    # Prod's column is INTEGER, but the model has always declared a float and
    # SQLite type affinity accepts both. Left as FloatField to match the model.
    ttl = fields.FloatField()

    class Meta:
        table = "fishbowl_config"
