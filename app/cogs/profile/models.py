from tortoise import fields
from tortoise.models import Model


class ProfileLink(Model):
    id = fields.IntField(primary_key=True)
    user_id = fields.IntField()
    service = fields.CharField(max_length=255)
    url = fields.CharField(max_length=255)

    class Meta:
        table = "user_profile_links"
        unique_together = (("user_id", "service"),)


class UserProfile(Model):
    id = fields.IntField(primary_key=True)
    user_id = fields.IntField()
    name = fields.CharField(max_length=255)
    description = fields.TextField(null=True)
    # Was stamped with utcnow() by a save() override under Peewee; auto_now is
    # the Tortoise equivalent (applied application-side on every save).
    last_updated = fields.DatetimeField(auto_now=True)
    is_default = fields.BooleanField(default=False)
    is_nsfw = fields.BooleanField(default=False)

    class Meta:
        table = "user_profiles"
        unique_together = (("user_id", "name"),)


class UserProfilesConfig(Model):
    id = fields.IntField(primary_key=True)
    guild_id = fields.IntField(unique=True)
    enabled = fields.BooleanField(default=False)

    class Meta:
        table = "user_profiles_config"
