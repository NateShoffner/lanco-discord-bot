from db import BaseModel
from peewee import BigIntegerField, DateTimeField, TextField


class TrendingChannelConfig(BaseModel):
    """A channel whose name and topic follow the conversation.

    One row per enabled channel; disabling deletes the row. A guild may have
    any number of them.
    """

    guild_id = BigIntegerField()
    channel_id = BigIntegerField(unique=True)
    enabled_by = BigIntegerField(null=True)
    # the channel's last_message_id when history was last fetched, so an idle
    # channel costs no API call at all on each poll
    last_seen_message_id = BigIntegerField(null=True)
    # newest message included in the last analysis, so only messages after
    # it count toward the new-message threshold
    last_analyzed_message_id = BigIntegerField(null=True)
    # when the channel was last analyzed; the cooldown is measured from here
    # and survives restarts, so a redeploy cannot burn through Discord's
    # two-edits-per-ten-minutes bucket
    last_updated_at = DateTimeField(null=True)
    last_name = TextField(null=True)
    last_topic = TextField(null=True)

    class Meta:
        table_name = "trending_channel_config"
