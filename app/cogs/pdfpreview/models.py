from tortoise import fields
from tortoise.models import Model


class PDFPreviewConfig(Model):
    id = fields.IntField(primary_key=True)
    guild_id = fields.IntField(unique=True)
    enabled = fields.BooleanField(default=False)
    preview_pages = fields.IntField(default=1)
    virus_check = fields.BooleanField(default=True)

    class Meta:
        table = "pdf_preview_config"
