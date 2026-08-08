from cogs.common.embedfixcog import GuildPkEmbedFixConfig
from tortoise import fields
from tortoise.models import Model


class PaywallBypassConfig(GuildPkEmbedFixConfig):
    class Meta:
        table = "paywall_bypass_config"


class PaywallPattern(Model):
    id = fields.IntField(primary_key=True)
    # db_index reflects the model's original intent; the live table has no such
    # index (migration 018 created the table without one). Creating it is
    # non-destructive and the table is empty, so it is safe to reconcile.
    guild_id = fields.BigIntField(db_index=True)
    pattern = fields.CharField(max_length=255)

    class Meta:
        table = "paywall_pattern"
