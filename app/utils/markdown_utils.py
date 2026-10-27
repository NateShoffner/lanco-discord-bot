import re

import discord
from bs4 import BeautifulSoup


def _looks_like_html(text: str) -> bool:
    return bool(re.search(r"<[a-zA-Z][^>]*>", text))


def escape_markdown(text: str) -> str:
    """Neutralize Discord markdown in text that should be read literally.

    Anything quoted from somewhere else (a username, a place name, a track
    title) is plain text at the source and formatting here, so the Reddit
    user `spell_i_cup` renders as "spellicup" with an italic i. Use this
    wherever external text lands in an embed description or field value;
    embed titles, author names, and footers do not render markdown and do
    not need it.
    """
    if not text:
        return text
    return discord.utils.escape_markdown(text)


def escape_link_label(text: str) -> str:
    """Escape text used as the label of a ``[label](url)`` link.

    A label has to survive the brackets as well as the usual formatting
    characters, which ``escape_markdown`` leaves alone: an unescaped ``]``
    closes the label early and lets the rest of the external text supply its
    own URL.
    """
    if not text:
        return text
    return escape_markdown(text).replace("[", r"\[").replace("]", r"\]")


def markdown_link(label: str, url: str, *, suppress_embed: bool = False) -> str:
    """Build a ``[label](url)`` link that external text cannot break out of.

    Parentheses in the URL are percent-encoded because a bare ``)`` ends the
    link target, which is a real shape for article URLs. ``suppress_embed``
    wraps the target in angle brackets so Discord does not unfurl it.
    """
    target = url.replace("(", "%28").replace(")", "%29")
    if suppress_embed:
        target = f"<{target}>"
    return f"[{escape_link_label(label)}]({target})"


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

    if _looks_like_html(text):
        text = html_to_markdown(text)

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


def html_to_markdown(html: str) -> str:
    """
    Convert HTML content to Markdown format.

    Args:
        html (str): The HTML content to convert.

    Returns:
        str: The converted Markdown content.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Convert links
    for a in soup.find_all("a", href=True):
        a.replace_with(f"[{a.get_text()}]({a['href']})")

    # Convert bold text
    for b in soup.find_all(["b", "strong"]):
        b.replace_with(f"**{b.get_text()}**")

    # Convert italic text
    for i in soup.find_all(["i", "em"]):
        i.replace_with(f"*{i.get_text()}*")

    # Convert line breaks and paragraphs
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for p in soup.find_all("p"):
        p.insert_before("\n\n")
        p.insert_after("\n\n")

    # Get the text and clean up extra whitespace
    markdown = soup.get_text()
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)  # Limit consecutive newlines to 2
    markdown = markdown.strip()

    return markdown
