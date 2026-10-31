"""Markdown escaping for text quoted from outside Discord."""

from types import SimpleNamespace

from cogs.redditfeed.redditfeed import format_crosspost, format_link, format_poll
from utils.markdown_utils import escape_link_label, escape_markdown, markdown_link


def test_underscores_survive_as_characters():
    assert escape_markdown("spell_i_cup") == "spell\_i\_cup"


def test_other_formatting_characters_are_escaped():
    assert escape_markdown("**bold**") == "\*\*bold\*\*"
    assert escape_markdown("a|b") == "a\|b"
    assert escape_markdown("back`tick") == "back\`tick"


def test_empty_text_is_left_alone():
    assert escape_markdown("") == ""
    assert escape_link_label("") == ""


def test_a_label_cannot_close_its_own_brackets():
    label = escape_link_label("x](https://evil.example)")
    assert label == "x\](https://evil.example)"
    assert markdown_link("x](https://evil.example)", "https://reddit.com/u/x") == (
        "[x\](https://evil.example)](https://reddit.com/u/x)"
    )


def test_link_keeps_the_label_inside_the_link():
    link = markdown_link("spell_i_cup", "https://reddit.com/u/spell_i_cup")
    assert link == "[spell\_i\_cup](https://reddit.com/u/spell_i_cup)"


def test_parentheses_in_the_url_do_not_end_the_link():
    link = markdown_link("wiki", "https://en.wikipedia.org/wiki/Mercury_(planet)")
    assert link == "[wiki](https://en.wikipedia.org/wiki/Mercury_%28planet%29)"


def test_suppressed_embed_wraps_the_target():
    assert (
        markdown_link("cnn.com", "https://cnn.com/a") == "[cnn.com](https://cnn.com/a)"
    )
    assert (
        markdown_link("cnn.com", "https://cnn.com/a", suppress_embed=True)
        == "[cnn.com](<https://cnn.com/a>)"
    )


def test_self_post_domain_carries_the_subreddit_name():
    # a self post's domain is `self.<subreddit>`, underscores included
    post = SimpleNamespace(
        is_self=False,
        url="https://reddit.com/r/not_the_onion/comments/abc",
        domain="self.not_the_onion",
    )
    assert format_link(post) == (
        "[self.not\_the\_onion]" "(<https://reddit.com/r/not_the_onion/comments/abc>)"
    )


def test_crosspost_subreddit_name_is_escaped():
    post = SimpleNamespace(
        crosspost_parent_list=[
            {
                "subreddit_name_prefixed": "r/not_the_onion",
                "permalink": "/r/not_the_onion/comments/abc/",
            }
        ]
    )
    assert format_crosspost(post) == (
        "[/r/not\_the\_onion](https://reddit.com/r/not_the_onion/comments/abc/)"
    )


def test_poll_options_are_read_literally():
    poll = SimpleNamespace(
        poll_data={
            "options": [{"text": "a_b_c"}, {"text": "**loud**"}],
            "total_vote_count": 2,
        }
    )
    assert format_poll(poll) == "- a\_b\_c\n- \*\*loud\*\*\n2 votes"
