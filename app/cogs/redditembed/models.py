from cogs.common.embedfixcog import EmbedFixConfigBase


class RedditEmbedConfig(EmbedFixConfigBase):
    class Meta:
        table_name = "redditembed_config"
