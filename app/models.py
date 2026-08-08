import datetime

from tortoise import fields
from tortoise.models import Model


class BlacklistedUser(Model):
    # generated=False is required: this PK is an application-supplied Discord
    # snowflake, not a generated sequence. Without it Tortoise emits
    # "INTEGER PRIMARY KEY AUTOINCREMENT", which silently downgrades BIGINT to
    # INTEGER and makes create() with no user_id succeed with user_id=1 rather
    # than raising. Applies to every snowflake-keyed model in this codebase.
    user_id = fields.BigIntField(primary_key=True, generated=False)
    reason = fields.TextField(null=True)
    created_at = fields.DatetimeField(default=datetime.datetime.now)

    class Meta:
        table = "blacklisted_users"
