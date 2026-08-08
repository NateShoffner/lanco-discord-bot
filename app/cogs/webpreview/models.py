from tortoise import fields
from tortoise.models import Model


class WebPreviewConfig(Model):
    id = fields.IntField(primary_key=True)
    guild_id = fields.IntField(unique=True)
    enabled = fields.BooleanField(default=False)

    class Meta:
        table = "web_preview_config"
