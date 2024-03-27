from peewee import *
from cogs.common.embedfixcog import EmbedFixConfigBase


class PaywallBypassConfig(EmbedFixConfigBase):
    class Meta:
        table_name = "paywall_bypass_config"
