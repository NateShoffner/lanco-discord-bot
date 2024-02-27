from peewee import *
from cogs.common.embedfixcog import EmbedFixConfigBase


class TwitterEmbedConfig(EmbedFixConfigBase):
    class Meta:
        table_name = "twitterembed_config"
