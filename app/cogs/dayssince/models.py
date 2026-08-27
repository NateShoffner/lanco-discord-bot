from db import BaseModel
from peewee import *


class DaysSinceTracker(BaseModel):
    guild_id = BigIntegerField()
    command_name = CharField()
    title = CharField()
    event_label = CharField()
    last_event_at = DateTimeField(null=True)
    total_count = IntegerField(default=0)
    record_days = IntegerField(default=0)
    channel_id = BigIntegerField(null=True)
    author = BigIntegerField(null=True)
    last_updated = DateTimeField(null=True)

    class Meta:
        table_name = "days_since_trackers"
        # An autoincrement id rather than a composite key on
        # (guild_id, command_name), so a tracker can be renamed with a plain
        # save() instead of turning into a second row.
        indexes = ((("guild_id", "command_name"), True),)
