from db import BaseModel
from peewee import *


class WeatherUserConfig(BaseModel):
    user_id = IntegerField(unique=True)
    user_location = CharField(null=True)
    location = CharField(null=True)
    lon = FloatField(null=True)
    lat = FloatField(null=True)

    class Meta:
        table_name = "weather_user_config"
