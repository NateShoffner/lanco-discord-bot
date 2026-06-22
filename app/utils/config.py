import pytz
from db import BaseModel
from peewee import *


class GuildConfig(BaseModel):
    guild_id = IntegerField(unique=True)
    prefix = CharField(default=".")
    timezone = CharField(default="UTC")

    class Meta:
        table_name = "guild_configs"

    # helper method to convert timezone to pytz timezone
    def get_pytz_timezone(self):
        return pytz.timezone(self.timezone)


def get_guild_config(guild_id: int) -> GuildConfig:
    return GuildConfig.get_or_none(guild_id=guild_id)


class UserConfig(BaseModel):
    user_id = IntegerField()
    setting_name = CharField()
    setting_value = CharField()
    guild_id = IntegerField(null=True)

    def is_global_setting(self) -> bool:
        return self.guild_id is None

    class Meta:
        table_name = "user_configs"
