from tortoise import fields
from tortoise.models import Model


class Fact(Model):
    id = fields.IntField(primary_key=True)
    guild_id = fields.IntField()
    author_id = fields.IntField()
    last_modified = fields.DatetimeField()
    fact = fields.TextField()

    class Meta:
        table = "facts"
