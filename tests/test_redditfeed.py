"""Reddit feed embed content tests.

The helpers that decide what a post's embed shows are pure, so they can be
checked against the shapes Reddit actually returns without touching the API.
Each case here is a post type whose content used to be dropped: link posts
showed no link, and crossposts showed nothing at all.
"""

from types import SimpleNamespace

from cogs.redditfeed.redditfeed import (
    FIELD_VALUE_LIMIT,
    format_crosspost,
    format_link,
    format_media,
    format_poll,
    get_content_source,
    get_image_url,
)


def _submission(**kwargs):
    defaults = dict(is_self=False, selftext="", url="", domain="")
    return SimpleNamespace(**{**defaults, **kwargs})


def test_link_post_shows_its_destination():
    post = _submission(
        url="https://archives.fbi.gov/archives/press-releases/2013/operator",
        domain="archives.fbi.gov",
    )
    assert format_link(post) == (
        "[archives.fbi.gov]"
        "(<https://archives.fbi.gov/archives/press-releases/2013/operator>)"
    )


def test_link_strips_www_from_label():
    post = _submission(url="https://www.cnn.com/travel", domain="www.cnn.com")
    assert format_link(post) == "[cnn.com](<https://www.cnn.com/travel>)"


def test_reddit_hosted_content_is_not_a_link():
    assert format_link(_submission(is_self=True, url="https://reddit.com/r/x")) is None
    assert (
        format_link(_submission(url="https://i.redd.it/a.jpeg", domain="i.redd.it"))
        is None
    )
    assert (
        format_link(
            _submission(url="https://v.redd.it/abc", domain="v.redd.it", is_video=True)
        )
        is None
    )
    assert (
        format_link(
            _submission(
                url="https://www.reddit.com/gallery/abc",
                domain="reddit.com",
                is_gallery=True,
            )
        )
        is None
    )


def test_overlong_link_falls_back_to_plain_domain():
    # a markdown link cut off mid-url renders as broken text
    post = _submission(url="https://example.com/" + "a" * 2000, domain="example.com")
    assert format_link(post) == "example.com"
    assert len(format_link(post)) <= FIELD_VALUE_LIMIT


def test_crosspost_reads_content_from_parent():
    parent = {
        "subreddit": "Hersheypark",
        "subreddit_name_prefixed": "r/Hersheypark",
        "permalink": "/r/Hersheypark/comments/1wu3ydx/measles_cases/",
        "is_self": True,
        "selftext": "original body",
        "url": "https://www.reddit.com/r/Hersheypark/comments/1wu3ydx/measles_cases/",
    }
    # the crosspost itself has no body and a relative url
    post = _submission(
        url="/r/Hersheypark/comments/1wu3ydx/measles_cases/",
        crosspost_parent_list=[parent],
    )
    source = get_content_source(post)
    assert source["selftext"] == "original body"
    assert format_link(source) is None
    assert format_crosspost(post) == (
        "[/r/Hersheypark]"
        "(https://reddit.com/r/Hersheypark/comments/1wu3ydx/measles_cases/)"
    )


def test_crosspost_of_gallery_uses_parent_media():
    parent = {
        "subreddit_name_prefixed": "r/classiccars",
        "permalink": "/r/classiccars/comments/1wrq6au/show/",
        "is_gallery": True,
        "url": "https://www.reddit.com/gallery/1wrq6au",
        "domain": "reddit.com",
        "gallery_data": {"items": [{"media_id": "b"}, {"media_id": "a"}]},
        "media_metadata": {
            "a": {"status": "valid", "e": "Image", "s": {"u": "https://a"}},
            "b": {"status": "valid", "e": "Image", "s": {"u": "https://b"}},
        },
    }
    post = _submission(
        url="https://www.reddit.com/gallery/1wrq6au",
        domain="reddit.com",
        crosspost_parent_list=[parent],
    )
    source = get_content_source(post)
    # gallery order, not media_metadata order
    assert get_image_url(source) == "https://b"
    assert format_media(source) == "Gallery · 2 images"
    assert format_link(source) is None


def test_non_crosspost_is_its_own_source():
    post = _submission(is_self=True, selftext="body")
    assert get_content_source(post) is post
    assert format_crosspost(post) is None


def test_media_label_for_video():
    post = _submission(
        is_video=True, media={"reddit_video": {"duration": 73, "is_gif": False}}
    )
    assert format_media(post) == "Video · 1:13"
    assert format_media(_submission(is_video=True, media=None)) == "Video"
    assert format_media(_submission(is_self=True)) is None


def test_image_falls_back_to_preview():
    post = _submission(preview={"images": [{"source": {"url": "https://p"}}]})
    assert get_image_url(post) == "https://p"
    assert get_image_url(_submission()) is None
    assert get_image_url(_submission(preview={"images": []})) is None


def test_image_skips_invalid_gallery_items():
    post = _submission(
        gallery_data={"items": [{"media_id": "a"}, {"media_id": "b"}]},
        media_metadata={
            "a": {"status": "failed"},
            "b": {"status": "valid", "e": "Image", "s": {"u": "https://b"}},
        },
    )
    assert get_image_url(post) == "https://b"


def test_poll_lists_options_and_votes():
    poll = SimpleNamespace(
        options=[SimpleNamespace(text="Yes"), SimpleNamespace(text="No")],
        total_vote_count=1,
    )
    assert format_poll(_submission(poll_data=poll)) == "- Yes\n- No\n1 vote"
    assert format_poll(_submission()) is None
