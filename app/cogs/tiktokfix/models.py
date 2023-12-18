from peewee import *

from db import BaseModel


class TikTokFixConfig(BaseModel):
    guild_id = IntegerField(unique=True)
    enabled = BooleanField(default=False)

    class Meta:
        table_name = "tiktokfix_config"
