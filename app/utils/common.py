import logging

import emoji
import regex

logger = logging.getLogger(__name__)

# A stored pattern runs against every message, and the stdlib re cannot abandon
# a match in progress. regex can.
MATCH_TIMEOUT = 0.1
MAX_MATCH_INPUT = 4000


def is_regex(string: str) -> bool:
    try:
        regex.compile(string)
    except regex.error:
        return False
    return True


def is_safe_regex(pattern: str) -> bool:
    """Reject a pattern that cannot be matched inside the per-message deadline.

    Compiling only proves it parses, so run it against filler too.
    """
    if not is_regex(pattern):
        return False
    probe = "a" * 200 + "!" + "0" * 200
    try:
        regex.search(pattern, probe, timeout=MATCH_TIMEOUT)
    except TimeoutError:
        return False
    return True


# warned once per pattern, since this runs on every message
_warned_patterns = set()


def matches_pattern(pattern: str, text: str) -> bool:
    """Match a stored pattern under a deadline, False if malformed or too slow."""
    try:
        return (
            regex.search(pattern, text[:MAX_MATCH_INPUT], timeout=MATCH_TIMEOUT)
            is not None
        )
    except (regex.error, TimeoutError) as e:
        if pattern not in _warned_patterns:
            _warned_patterns.add(pattern)
            logger.warning(f"Ignoring pattern {pattern!r}: {e}")
        return False


def is_emoji(response: str):
    if emoji.emoji_count(response) > 0:
        return True
    return response.startswith("<:") and response.endswith(">")
