from cogs.common.embedfixcog import EmbedFixConfigBase
from peewee import *


class PaywallBypassConfig(EmbedFixConfigBase):
    class Meta:
        table_name = "paywall_bypass_config"
