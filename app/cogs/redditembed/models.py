from cogs.common.embedfixcog import GuildPkEmbedFixConfig


class RedditEmbedConfig(GuildPkEmbedFixConfig):
    class Meta:
        table = "redditembed_config"
