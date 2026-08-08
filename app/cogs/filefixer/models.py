from tortoise import fields
from tortoise.models import Model


class FileFixerConfig(Model):
    guild_id = fields.BigIntField(primary_key=True, generated=False)
    enabled = fields.BooleanField(default=False)

    class Meta:
        table = "file_fixer_config"
