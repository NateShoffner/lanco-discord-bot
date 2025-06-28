from discord import Message, TextChannel


async def get_user_messages(
    channel: TextChannel, limit: int, oldest_first: bool = False
) -> list[Message]:
    """Get strictly text messages from users in a channel"""

    messages = [
        msg async for msg in channel.history(limit=limit, oldest_first=oldest_first)
    ]
    messages = [
        m
        for m in messages
        if not m.author.bot  # Ignore bot messages
        and m.content.strip() != ""  # Ignore empty messages
        and not m.content.startswith(".")  # TODO we need to ignore all bot commands
    ]

    # TODO allow filtering for spoilered messages

    return messages
