from peewee import *

from db import BaseModel


class TwitterEmbedConfig(BaseModel):
    guild_id = IntegerField(unique=True)
    enabled = BooleanField(default=False)

    class Meta:
        table_name = "twitterembed_config"
