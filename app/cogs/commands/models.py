from tortoise import fields
from tortoise.models import Model


class CustomCommands(Model):
    # NOTE: no unique_together on (guild_id, command_name). The live table has
    # never had a primary key or any index, so the composite key the Peewee
    # model declared was never actually enforced. Restoring that guarantee is a
    # separate, deliberate change and is tracked on its own; do not add it here.
    id = fields.IntField(primary_key=True)
    guild_id = fields.IntField()
    command_name = fields.CharField(max_length=255)
    command_response = fields.CharField(max_length=255, null=True)
    channel_id = fields.IntField(null=True)
    command_type = fields.CharField(max_length=255, default="basic")
    last_updated = fields.DatetimeField(null=True)
    author = fields.BigIntField(null=True)
    cooldown = fields.IntField(default=0)
    last_used = fields.DatetimeField(null=True)
    owner = fields.BigIntField(null=True)

    class Meta:
        table = "custom_commands"
