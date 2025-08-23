import re

from bs4 import BeautifulSoup


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
