from db import BaseModel
from peewee import *


class FixItConfig(BaseModel):
    guild_id = BigIntegerField(primary_key=True)
    channel_id = BigIntegerField()
    last_known_issue = IntegerField(null=True)

    class Meta:
        table_name = "fixit_config"
