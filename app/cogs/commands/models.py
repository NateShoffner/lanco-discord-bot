from db import BaseModel
from peewee import *


class CustomCommands(BaseModel):
    guild_id = IntegerField()
    command_name = CharField()
    command_response = CharField()
    channel_id = IntegerField(null=True)

    class Meta:
        table_name = "custom_commands"
        primary_key = CompositeKey("guild_id", "command_name")
