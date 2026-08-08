from tortoise import fields
from tortoise.models import Model


class BirthdayAnnouncementConfig(Model):
    id = fields.IntField(primary_key=True)
    guild_id = fields.IntField()
    channel_id = fields.IntField()

    class Meta:
        table = "birthday_announcement_config"


class BirthdayUser(Model):
    id = fields.IntField(primary_key=True)
    guild_id = fields.IntField()
    user_id = fields.IntField()
    date = fields.DateField(null=True)

    class Meta:
        table = "birthday_user"
        unique_together = (("guild_id", "user_id"),)
