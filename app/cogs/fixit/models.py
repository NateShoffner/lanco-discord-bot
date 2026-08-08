from tortoise import fields
from tortoise.models import Model


class FixItConfig(Model):
    guild_id = fields.BigIntField(primary_key=True, generated=False)
    channel_id = fields.BigIntField()
    last_known_issue = fields.IntField(null=True)

    class Meta:
        table = "fixit_config"
