from peewee import *

from db import BaseModel


class TwitterFixConfig(BaseModel):
    guild_id = IntegerField(unique=True)
    enabled = BooleanField(default=False)

    class Meta:
        table_name = "twitterfix_config"
