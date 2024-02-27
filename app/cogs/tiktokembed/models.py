from peewee import *
from cogs.common.embedfixcog import EmbedFixConfigBase


class TikTokEmbedConfig(EmbedFixConfigBase):
    class Meta:
        table_name = "tiktokembed_config"
