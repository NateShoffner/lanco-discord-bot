from peewee import *

from db import BaseModel


class SpotifyEmbedConfig(BaseModel):
    guild_id = IntegerField(unique=True)
    enabled = BooleanField(default=False)

    class Meta:
        table_name = "spotify_embed_config"
