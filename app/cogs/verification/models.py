from db import BaseModel
from peewee import *


class VerificationConfig(BaseModel):
    guild_id = IntegerField(unique=True)
    mod_channel_id = IntegerField(null=True)
    verified_role_id = IntegerField(null=True)
    vote_threshold = IntegerField(default=3)
    vote_duration = IntegerField(default=60)

    class Meta:
        table_name = "verification_config"


class VerificationRequest(BaseModel):
    user_id = IntegerField()
    message_id = IntegerField()
    guild_id = IntegerField()
    approvals = IntegerField(default=0)
    denials = IntegerField(default=0)
    pending = BooleanField(default=True)

    class Meta:
        table_name = "verification_requests"
