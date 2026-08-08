from functools import wraps

import discord
from tortoise import fields
from tortoise.models import Model


class TrackedMessage(Model):
    # A Discord message snowflake, supplied by the caller. generated=False keeps
    # Tortoise from emitting AUTOINCREMENT (which would also silently accept a
    # create() with no message_id and assign it 1).
    message_id = fields.BigIntField(primary_key=True, generated=False)

    class Meta:
        table = "tracked_messages"


async def is_message_tracked(message_id: int) -> bool:
    """Check if a message is tracked"""
    return await TrackedMessage.get_or_none(message_id=message_id)


def track_message_ids():
    """A decorator to track message ids"""

    def decorator(func):
        @wraps(func)
        async def wrapper(self, ctx, *args, **kwargs):
            # Call the original command
            result = await func(self, ctx, *args, **kwargs)

            # After the command execution, track the message ID
            if result and isinstance(result, discord.Message):
                await TrackedMessage.create(message_id=result.id)

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
                if await is_message_tracked(referenced_message_id):
                    return

            # Call the original command
            return await func(self, ctx, *args, **kwargs)

        return wrapper

    return decorator
