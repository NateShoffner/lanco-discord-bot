from peewee import *

from db import BaseModel


class TikTokEmbedConfig(BaseModel):
    guild_id = IntegerField(unique=True)
    enabled = BooleanField(default=False)

    class Meta:
        table_name = "tiktokembed_config"
