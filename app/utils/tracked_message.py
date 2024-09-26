from functools import wraps

import discord
from db import BaseModel
from peewee import *


class TrackedMessage(BaseModel):
    message_id = IntegerField(primary_key=True)

    class Meta:
        table_name = "tracked_messages"


def create_tables():
    """Create the tables"""
    with BaseModel._meta.database:
        BaseModel._meta.database.create_tables([TrackedMessage])


def is_message_tracked(message_id: int) -> bool:
    """Check if a message is tracked"""
    create_tables()
    return TrackedMessage.get_or_none(message_id=message_id)


def track_message_ids():
    """A decorator to track message ids"""

    def decorator(func):
        @wraps(func)
        async def wrapper(self, ctx, *args, **kwargs):

            create_tables()

            # Call the original command
            result = await func(self, ctx, *args, **kwargs)

            # After the command execution, track the message ID
            if result and isinstance(result, discord.Message):
                TrackedMessage.create(message_id=result.id)

            return result

        return wrapper

    return decorator


def ignore_if_referenced_message_is_tracked():
    """A decorator to ignore the command if the referenced message is already tracked"""

    def decorator(func):
        @wraps(func)
        async def wrapper(self, ctx, *args, **kwargs):

            msg = None

            if isinstance(ctx, discord.Message):
                msg = ctx
            if (
                hasattr(ctx, "message")
                and ctx.message
                and isinstance(ctx.message, discord.Message)
            ):
                msg = ctx.message

            if not msg:  # for other types of context, just return
                return

            if msg.reference:
                referenced_message_id = msg.reference.message_id
                if is_message_tracked(referenced_message_id):
                    return

            # Call the original command
            return await func(self, ctx, *args, **kwargs)

        return wrapper

    return decorator
