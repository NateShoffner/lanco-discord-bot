import datetime

from db import BaseModel
from peewee import *


class ProfileLink(BaseModel):
    user_id = IntegerField()
    service = CharField()
    url = CharField()

    class Meta:
        table_name = "user_profile_links"
        primary_key = CompositeKey("user_id", "service")


class UserProfile(BaseModel):
    user_id = IntegerField()
    name = CharField()
    description = TextField(null=True)
    last_updated = DateTimeField()
    is_default = BooleanField(default=False)
    is_nsfw = BooleanField(default=False)

    def save(self, *args, **kwargs):
        self.last_updated = datetime.datetime.utcnow()
        return super().save(*args, **kwargs)

    class Meta:
        table_name = "user_profiles"
        primary_key = CompositeKey("user_id", "name")


class UserProfilesConfig(BaseModel):
    guild_id = IntegerField(unique=True)
    enabled = BooleanField(default=False)

    class Meta:
        table_name = "user_profiles_config"
