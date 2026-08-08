import pytz
from tortoise import fields
from tortoise.models import Model


class GuildConfig(Model):
    id = fields.IntField(primary_key=True)
    guild_id = fields.IntField(unique=True)
    prefix = fields.CharField(max_length=255, default=".")
    timezone = fields.CharField(max_length=255, default="UTC")

    class Meta:
        table = "guild_configs"

    # helper method to convert timezone to pytz timezone
    def get_pytz_timezone(self):
        return pytz.timezone(self.timezone)


async def get_guild_config(guild_id: int) -> GuildConfig:
    return await GuildConfig.get_or_none(guild_id=guild_id)


class UserConfig(Model):
    id = fields.IntField(primary_key=True)
    user_id = fields.IntField()
    setting_name = fields.CharField(max_length=255)
    setting_value = fields.CharField(max_length=255)
    guild_id = fields.IntField(null=True)

    def is_global_setting(self) -> bool:
        return self.guild_id is None

    class Meta:
        table = "user_configs"
