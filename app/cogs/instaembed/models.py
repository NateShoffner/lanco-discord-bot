from peewee import *

from db import BaseModel


class InstaEmbedConfig(BaseModel):
    guild_id = IntegerField(unique=True)
    enabled = BooleanField(default=False)

    class Meta:
        table_name = "instaembed_config"
