from cogs.common.embedfixcog import GuildPkEmbedFixConfig


class FacebookEmbedConfig(GuildPkEmbedFixConfig):
    class Meta:
        table = "facebookembed_config"
