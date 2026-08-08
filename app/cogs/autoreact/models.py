from tortoise import fields
from tortoise.models import Model


class AutoReactConfig(Model):
    id = fields.IntField(primary_key=True)
    phrase = fields.CharField(max_length=255)
    emoji = fields.CharField(max_length=255)
    is_regex = fields.BooleanField(default=False)
    guild_id = fields.BigIntField()

    class Meta:
        table = "auto_react"
