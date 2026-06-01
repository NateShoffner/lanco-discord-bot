import re

from bs4 import BeautifulSoup


def reddit_to_discord(text: str) -> str:
    """
    Convert Reddit markdown to Discord-compatible markdown.

    Handles Reddit-specific syntax that Discord doesn't support or
    renders differently.

    Args:
        text (str): Reddit markdown text.

    Returns:
        str: Discord-compatible markdown text.
    """
    if not text:
        return text

    # Spoilers: >!text!< -> ||text||
    text = re.sub(r">!(.*?)!<", r"||\1||", text)

    # Headers: # Header -> **Header** (Discord embeds don't render headers)
    text = re.sub(r"^#{1,6}\s+(.+)$", r"**\1**", text, flags=re.MULTILINE)

    # Superscript: ^word or ^(phrase) -> (word)
    text = re.sub(r"\^\(([^)]+)\)", r"(\1)", text)
    text = re.sub(r"\^(\S+)", r"(\1)", text)

    # Horizontal rules: --- or *** on their own line -> strip
    text = re.sub(r"^(-{3,}|\*{3,})$", "", text, flags=re.MULTILINE)

    # Reddit tables: strip them down to plain text (Discord embeds don't render tables)
    # Remove table separator rows (|---|---|)
    text = re.sub(r"^\|[\s\-|:]+\|$", "", text, flags=re.MULTILINE)

    # Cleanup extra blank lines left behind
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return text
