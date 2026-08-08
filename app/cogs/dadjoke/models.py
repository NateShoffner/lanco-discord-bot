from tortoise import fields
from tortoise.models import Model


class DadJokeConfig(Model):
    id = fields.IntField(primary_key=True)
    enabled = fields.BooleanField(default=False)
    channel_id = fields.IntField(unique=True)

    class Meta:
        table = "dadjoke_configs"


class NameChange(Model):
    id = fields.IntField(primary_key=True)
    guild_id = fields.IntField()
    user_id = fields.IntField()
    old_name = fields.CharField(max_length=255)
    new_name = fields.CharField(max_length=255)
    # Was a DB-side `DEFAULT CURRENT_TIMESTAMP` under Peewee; auto_now_add is
    # the Tortoise equivalent (applied application-side on insert).
    timestamp = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "name_changes"
