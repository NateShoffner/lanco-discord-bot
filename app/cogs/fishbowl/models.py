from db import BaseModel
from peewee import *


class FishbowlConfig(BaseModel):
    channel_id = IntegerField()
    ttl = FloatField()

    class Meta:
        table_name = "fishbowl_config"
