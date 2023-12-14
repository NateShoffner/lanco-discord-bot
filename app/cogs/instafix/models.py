from peewee import *

from db import BaseModel


class InstaFixConfig(BaseModel):
    guild_id = IntegerField(unique=True)
    enabled = BooleanField(default=False)

    class Meta:
        table_name = "instafix_config"
