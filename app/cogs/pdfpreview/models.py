from db import BaseModel
from peewee import *


class PDFPreviewConfig(BaseModel):
    guild_id = IntegerField(unique=True)
    enabled = BooleanField(default=False)
    preview_pages = IntegerField(default=1)
    virus_check = BooleanField(default=True)

    class Meta:
        table_name = "pdf_preview_config"
