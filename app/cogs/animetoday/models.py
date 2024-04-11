from db import BaseModel
from peewee import *


class AnimeTodayConfig(BaseModel):
    guild_id = IntegerField()
    channel_id = IntegerField(null=True)

    class Meta:
        table_name = "anime_today_config"
