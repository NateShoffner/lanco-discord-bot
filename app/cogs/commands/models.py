from db import BaseModel
from peewee import *


class CustomCommands(BaseModel):
    guild_id = IntegerField()
    command_name = CharField()
    command_response = CharField(null=True)
    channel_id = IntegerField(null=True)
    command_type = CharField(default="basic")
    last_updated = DateTimeField(null=True)
    author = BigIntegerField(null=True)
    cooldown = IntegerField(default=0)
    last_used = DateTimeField(null=True)
    owner = BigIntegerField(null=True)

    class Meta:
        table_name = "custom_commands"
        primary_key = CompositeKey("guild_id", "command_name")
