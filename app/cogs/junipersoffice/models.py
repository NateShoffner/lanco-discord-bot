from db import BaseModel
from peewee import *


class FishTankConfig(BaseModel):
    guild_id = BigIntegerField(unique=True)
    last_death_at = DateTimeField(null=True)
    total_deaths = IntegerField(default=0)
    record_days = IntegerField(default=0)

    class Meta:
        table_name = "junipers_office_fish_tank"
