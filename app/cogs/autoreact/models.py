from db import BaseModel
from peewee import *


class AutoReactConfig(BaseModel):
    phrase = CharField()
    emoji = CharField()
    is_regex = BooleanField(default=False)
    guild_id = BigIntegerField()

    class Meta:
        table_name = "auto_react"
