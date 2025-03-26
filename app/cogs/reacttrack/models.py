from db import BaseModel
from peewee import *


class ReactEvent(BaseModel):
    message_id = IntegerField()
    channel_id = IntegerField()
    guild_id = IntegerField()
    user_id = IntegerField()
    emoji = CharField()
    timestamp = DateTimeField()
    added = BooleanField()

    class Meta:
        table_name = "react_events"
