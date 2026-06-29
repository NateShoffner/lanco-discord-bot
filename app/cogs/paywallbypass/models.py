from cogs.common.embedfixcog import EmbedFixConfigBase
from db import BaseModel
from peewee import *


class PaywallBypassConfig(EmbedFixConfigBase):
    class Meta:
        table_name = "paywall_bypass_config"


class PaywallPattern(BaseModel):
    guild_id = BigIntegerField(index=True)
    pattern = CharField()

    class Meta:
        table_name = "paywall_pattern"
