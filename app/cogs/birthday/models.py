from db import BaseModel
from peewee import *


class BirthdayAnnouncementConfig(BaseModel):
    guild_id = IntegerField()
    channel_id = IntegerField()

    class Meta:
        table_name = "birthday_announcement_config"


class BirthdayUser(BaseModel):
    guild_id = IntegerField()
    user_id = IntegerField()
    date = DateField(null=True)

    class Meta:
        table_name = "birthday_user"
        primary_key = CompositeKey("guild_id", "user_id")
