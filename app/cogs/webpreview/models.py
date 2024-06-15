from db import BaseModel
from peewee import *


class WebPreviewConfig(BaseModel):
    guild_id = IntegerField(unique=True)
    enabled = BooleanField(default=False)

    class Meta:
        table_name = "web_preview_config"
