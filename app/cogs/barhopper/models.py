from db import BaseModel
from peewee import *


class Bar(BaseModel):
    bar_name = CharField()
    address = CharField()
    latitude = FloatField()
    longitude = FloatField()
    rating = FloatField(null=True)
    price_level = IntegerField(null=True)
    business_status = CharField(null=True)
    place_id = CharField()

    class Meta:
        table_name = "bars"
