from tortoise import fields
from tortoise.models import Model


class VerificationConfig(Model):
    id = fields.IntField(primary_key=True)
    guild_id = fields.IntField(unique=True)
    mod_channel_id = fields.IntField(null=True)
    verified_role_id = fields.IntField(null=True)
    vote_threshold = fields.IntField(default=3)
    vote_duration = fields.IntField(default=60)

    class Meta:
        table = "verification_config"


class VerificationRequest(Model):
    id = fields.IntField(primary_key=True)
    user_id = fields.IntField()
    message_id = fields.IntField()
    guild_id = fields.IntField()
    approvals = fields.IntField(default=0)
    denials = fields.IntField(default=0)
    pending = fields.BooleanField(default=True)

    class Meta:
        table = "verification_requests"
