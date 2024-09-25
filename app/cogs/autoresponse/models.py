from db import BaseModel
from peewee import *


class AutoResponseConfig(BaseModel):
    phrase = CharField()
    response = CharField()
    is_regex = BooleanField(default=False)
    guild_id = BigIntegerField()

    class Meta:
        table_name = "auto-response"
