from db import BaseModel
from peewee import *


class CounterConfig(BaseModel):
    guild_id = BigIntegerField(unique=True)
    channel_id = BigIntegerField(null=True)
    current_count = IntegerField(default=0)
    last_user_id = BigIntegerField(null=True)
    high_score = IntegerField(default=0)

    class Meta:
        table_name = "counter_config"
