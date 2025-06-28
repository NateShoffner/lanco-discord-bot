from db import BaseModel
from peewee import *


class DadJokeConfig(BaseModel):
    enabled = BooleanField(default=False)
    channel_id = IntegerField(unique=True)

    class Meta:
        table_name = "dadjoke_configs"


class NameChange(BaseModel):
    guild_id = IntegerField()
    user_id = IntegerField()
    old_name = CharField()
    new_name = CharField()
    timestamp = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])

    class Meta:
        table_name = "name_changes"
