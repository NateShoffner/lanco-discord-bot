from peewee import *

from db import BaseModel


class CustomCommands(BaseModel):
    guild_id = IntegerField()
    command_name = CharField()
    command_response = CharField()

    class Meta:
        table_name = "custom_commands"
        primary_key = CompositeKey("guild_id", "command_name")
