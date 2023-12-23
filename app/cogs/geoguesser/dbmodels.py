from uuid import uuid4
from peewee import *

from db import BaseModel


class GeoguesserLocation(BaseModel):
    id = UUIDField(primary_key=True, default=uuid4)
    mode = CharField()
    initial_lat = FloatField()
    initial_lng = FloatField()
    road_lat = FloatField()
    road_lng = FloatField()

    class Meta:
        table_name = "geoguesser_locations"
