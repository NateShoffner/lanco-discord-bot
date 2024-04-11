from cogs.common.embedfixcog import EmbedFixConfigBase
from peewee import *


class TwitterEmbedConfig(EmbedFixConfigBase):
    class Meta:
        table_name = "twitterembed_config"
