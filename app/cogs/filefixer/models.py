from db import BaseModel
from peewee import *


class FileFixerConfig(BaseModel):
    guild_id = BigIntegerField(primary_key=True)
    enabled = BooleanField(default=False)

    class Meta:
        table_name = "file_fixer_config"
