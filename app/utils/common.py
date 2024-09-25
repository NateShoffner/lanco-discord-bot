import re

import emoji


def is_regex(string: str) -> bool:
    try:
        re.compile(string)
    except re.error:
        return False
    return True


def is_emoji(response: str):
    if emoji.emoji_count(response) > 0:
        return True
    return response.startswith("<:") and response.endswith(">")
