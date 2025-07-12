from db import BaseModel
from peewee import *


class EverbridgeConfig(BaseModel):
    channel_id = IntegerField(null=True)
    last_event_date = DateTimeField(null=True)
    subscription_name = CharField(null=True)

    class Meta:
        table_name = "everbridge_config"
