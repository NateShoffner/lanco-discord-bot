from db import BaseModel
from peewee import *


class PDFPreviewConfig(BaseModel):
    guild_id = IntegerField(unique=True)
    enabled = BooleanField(default=False)

    class Meta:
        table_name = "pdf_preview_config"
