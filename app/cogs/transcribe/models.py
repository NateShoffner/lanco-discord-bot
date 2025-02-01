from db import BaseModel
from peewee import *


class TranscribeConfig(BaseModel):
    guild_id = BigIntegerField(primary_key=True)
    enabled = BooleanField(default=False)

    class Meta:
        table_name = "transcribe_config"
