from functools import wraps

__active_commands = {}


def is_command_channel_locked(channel_id: int, command_name: str) -> bool:
    """Check if a command is already running in the channel"""
    if __active_commands[channel_id].get(command_name, False):
        return True
    return False


def command_channel_lock():
    """Decorator to ensure a command can only be run once at a time per channel and per command."""

    def decorator(func):
        @wraps(func)
        async def wrapper(self, ctx, *args, **kwargs):
            channel_id = ctx.channel.id
            command_name = func.__name__

            # Initialize the nested dictionary if the channel_id is not in __active_commands
            if channel_id not in __active_commands:
                __active_commands[channel_id] = {}

            locked = is_command_channel_locked(channel_id, command_name)
            if locked:
                self.logger.info(
                    f"Command {command_name} is already running in channel: {channel_id}"
                )
                return

            # Mark the command as running
            __active_commands[channel_id][command_name] = True

            try:
                # Execute the original command
                await func(self, ctx, *args, **kwargs)
            finally:
                # Mark the command as not running
                __active_commands[channel_id][command_name] = False

        return wrapper

    return decorator
