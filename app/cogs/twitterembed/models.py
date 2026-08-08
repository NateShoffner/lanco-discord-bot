from cogs.common.embedfixcog import SurrogatePkEmbedFixConfig


class TwitterEmbedConfig(SurrogatePkEmbedFixConfig):
    class Meta:
        table = "twitterembed_config"
