from cogs.common.embedfixcog import EmbedFixConfigBase
from peewee import *


class TikTokEmbedConfig(EmbedFixConfigBase):
    class Meta:
        table_name = "tiktokembed_config"
