from db import BaseModel
from peewee import *


class SpotifyEmbedConfig(BaseModel):
    guild_id = IntegerField(unique=True)
    enabled = BooleanField(default=False)

    class Meta:
        table_name = "spotify_embed_config"
