from db import BaseModel
from peewee import *


class Fact(BaseModel):
    guild_id = IntegerField()
    author_id = IntegerField()
    last_modified = DateTimeField()
    fact = TextField()

    class Meta:
        table_name = "facts"
