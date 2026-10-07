"""Models cogs need at runtime. Importing them from main.py would re-execute it as a second module."""

import datetime

from db import BaseModel
from peewee import BigIntegerField, DateTimeField, TextField


class BlacklistedUser(BaseModel):
    user_id = BigIntegerField(primary_key=True)
    reason = TextField(null=True)
    created_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "blacklisted_users"
