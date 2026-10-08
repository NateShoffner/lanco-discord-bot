"""A feed item the bot cannot post must not wedge the feed behind it.

All four polling cogs advanced their dedupe watermark only after a whole batch
sent successfully. One item that raised (an embed over Discord's limits, a
revoked permission, a malformed entry) therefore left the watermark where it
was, so the next poll re-fetched the same batch, re-posted every item before
the bad one, and failed again. `rssfeed` polls every ten seconds.

The ordering half matters just as much: these feeds hand back newest-first, and
a watermark advanced from the newest item in a page marks every older item in
that same page as already seen.
"""

import datetime
from types import SimpleNamespace

import pytest
from cogs.everbridge.everbridge import Everbridge
from cogs.fixit.fixit import FixIt
from cogs.redditfeed.redditfeed import RedditFeed, normalize_subreddit_name
from cogs.rssfeed.rssfeed import RssFeed
from feedparser.util import FeedParserDict


class _StubBot:
    def __init__(self, channel=None):
        self.channel = channel
        self.database = None

    def get_channel(self, channel_id):
        return self.channel


class _Channel:
    """A channel that refuses to send the nth message it is given."""

    def __init__(self, fail_on=None):
        self.sent = []
        self.fail_on = fail_on

    async def send(self, *args, **kwargs):
        self.sent.append(kwargs.get("embed", args[0] if args else None))
        if self.fail_on is not None and len(self.sent) == self.fail_on:
            raise RuntimeError("discord said no")
        return SimpleNamespace(id=len(self.sent))


# ---------------------------------------------------------------------------
# rssfeed
# ---------------------------------------------------------------------------


def _entry(title, published):
    # the real type feedparser hands the cog: dict access and attribute access
    return FeedParserDict(
        {
            "title": title,
            "link": f"https://example.com/{title}",
            "description": title,
            "published_parsed": published.timetuple(),
        }
    )


def _feed(entries):
    return SimpleNamespace(
        entries=entries, feed=SimpleNamespace(title="Example Feed"), bozo=False
    )


class _Config:
    """Stands in for a peewee row: attribute access plus a counting save()."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.saves = 0

    def save(self):
        self.saves += 1


async def _poll_once(cog):
    """Run the real loop body, bypassing the tasks.Loop wrapper."""
    await RssFeed.poll.coro(cog)


def _rssfeed(monkeypatch, entries, configs, channel):
    cog = RssFeed.__new__(RssFeed)
    RssFeed.__init__(cog, _StubBot(channel))
    monkeypatch.setattr(cog, "get_feed", _async_return(_feed(entries)))
    monkeypatch.setattr("cogs.rssfeed.rssfeed.RSSFeedConfig", _ConfigTable(configs))
    return cog


@pytest.mark.asyncio
async def test_rssfeed_advances_past_an_item_it_cannot_post(monkeypatch):
    base = datetime.datetime(2026, 6, 1, 12, 0)
    entries = [
        _entry(f"item{i}", base + datetime.timedelta(minutes=i)) for i in range(1, 5)
    ]
    channel = _Channel(fail_on=2)
    config = _Config(channel_id=1, url="https://example.com/feed", last_checked=base)
    cog = _rssfeed(monkeypatch, entries, [config], channel)

    await _poll_once(cog)

    # every item was attempted, including the ones queued behind the failure
    assert len(channel.sent) == 4
    # and the watermark moved past them rather than staying at the batch start
    assert config.last_checked > base + datetime.timedelta(minutes=4)


@pytest.mark.asyncio
async def test_rssfeed_posts_oldest_first(monkeypatch):
    """Feeds list newest first, and the watermark is a timestamp, so taking
    that order would mark the rest of the page as already seen.
    """
    base = datetime.datetime(2026, 6, 1, 12, 0)
    newest_first = [
        _entry(f"item{i}", base + datetime.timedelta(minutes=i)) for i in (3, 2, 1)
    ]
    channel = _Channel()
    config = _Config(channel_id=1, url="https://example.com/feed", last_checked=base)
    cog = _rssfeed(monkeypatch, newest_first, [config], channel)

    await _poll_once(cog)

    assert [e.title for e in channel.sent] == ["item1", "item2", "item3"]


@pytest.mark.asyncio
async def test_rssfeed_does_not_repost_on_the_next_poll(monkeypatch):
    """The whole point: a failure mid-batch used to replay the batch every ten
    seconds, re-posting everything before the bad item each time.
    """
    base = datetime.datetime(2026, 6, 1, 12, 0)
    entries = [
        _entry(f"item{i}", base + datetime.timedelta(minutes=i)) for i in range(1, 4)
    ]
    channel = _Channel(fail_on=2)
    config = _Config(channel_id=1, url="https://example.com/feed", last_checked=base)
    cog = _rssfeed(monkeypatch, entries, [config], channel)

    await _poll_once(cog)
    sent_after_first = len(channel.sent)
    channel.fail_on = None
    await _poll_once(cog)

    assert len(channel.sent) == sent_after_first, "the batch was replayed"


def test_rssfeed_entry_timestamp_tolerates_a_missing_date():
    cog = RssFeed.__new__(RssFeed)
    RssFeed.__init__(cog, _StubBot())
    assert cog.entry_timestamp(FeedParserDict({})) is None
    assert cog.entry_timestamp(
        FeedParserDict(
            {"updated_parsed": datetime.datetime(2026, 1, 2, 3, 4).timetuple()}
        )
    ) == datetime.datetime(2026, 1, 2, 3, 4)


@pytest.mark.asyncio
async def test_rssfeed_is_new_item_uses_the_same_timestamp_rule():
    cog = RssFeed.__new__(RssFeed)
    RssFeed.__init__(cog, _StubBot())
    watermark = datetime.datetime(2026, 6, 1, 12, 0)
    older = _entry("old", watermark - datetime.timedelta(minutes=1))
    newer = _entry("new", watermark + datetime.timedelta(minutes=1))

    assert await cog.is_new_item(older, watermark) is False
    assert await cog.is_new_item(newer, watermark) is True
    assert await cog.is_new_item(older, None) is True


# ---------------------------------------------------------------------------
# fixit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fixit_walks_issues_oldest_first(monkeypatch):
    """SeeClickFix returns newest first; taking that order marked the rest of
    the page as seen without posting it.
    """
    channel = _Channel()
    cog = FixIt.__new__(FixIt)
    FixIt.__init__(cog, _StubBot(channel))

    issues = [SimpleNamespace(id=i, summary=f"issue {i}") for i in (503, 502, 501)]
    config = _Config(guild_id=1, channel_id=1, last_known_issue=500)

    monkeypatch.setattr(
        cog, "client", SimpleNamespace(get_issues=_async_return(_issues(issues)))
    )
    monkeypatch.setattr("cogs.fixit.fixit.FixItConfig", _ConfigTable([config]))
    shared = []
    monkeypatch.setattr(cog, "share_issue", _record(shared))

    await cog.get_new_issues()

    assert [i.id for i in shared] == [501, 502, 503]
    assert config.last_known_issue == 503


@pytest.mark.asyncio
async def test_fixit_advances_past_an_issue_it_cannot_post(monkeypatch):
    cog = FixIt.__new__(FixIt)
    FixIt.__init__(cog, _StubBot(_Channel()))

    issues = [SimpleNamespace(id=i, summary=f"issue {i}") for i in (501, 502, 503)]
    config = _Config(guild_id=1, channel_id=1, last_known_issue=500)

    monkeypatch.setattr(
        cog, "client", SimpleNamespace(get_issues=_async_return(_issues(issues)))
    )
    monkeypatch.setattr("cogs.fixit.fixit.FixItConfig", _ConfigTable([config]))

    attempted = []

    async def share(issue, channel):
        attempted.append(issue.id)
        if issue.id == 502:
            raise RuntimeError("embed too long")

    monkeypatch.setattr(cog, "share_issue", share)

    await cog.get_new_issues()

    assert attempted == [501, 502, 503]
    assert config.last_known_issue == 503, "the bad issue blocked the ones after it"


def _issues(issues):
    return SimpleNamespace(issues=issues)


def _async_return(value):
    async def inner(*args, **kwargs):
        return value

    return inner


def _record(sink):
    async def inner(item, channel):
        sink.append(item)

    return inner


class _ConfigTable:
    """Stands in for a peewee model class, returning fixed rows from select()."""

    def __init__(self, rows):
        self._rows = rows

    def __call__(self):
        return self

    def select(self):
        return self._rows


# ---------------------------------------------------------------------------
# everbridge
# ---------------------------------------------------------------------------


def _notification(nid, created):
    return SimpleNamespace(id=nid, title=f"n{nid}", body="body", createdAt=created)


def _everbridge(channel, monkeypatch, notifications, configs):
    cog = Everbridge.__new__(Everbridge)
    monkeypatch.setenv("EVERBRIDGE_USERNAME", "u")
    monkeypatch.setenv("EVERBRIDGE_PASSWORD", "p")
    Everbridge.__init__(cog, _StubBot(channel))
    monkeypatch.setattr(
        cog,
        "client",
        SimpleNamespace(get_notifications=_async_return(notifications)),
    )
    monkeypatch.setattr(
        "cogs.everbridge.everbridge.EverbridgeConfig", _ConfigTable(configs)
    )
    return cog


@pytest.mark.asyncio
async def test_everbridge_seeds_an_unseeded_config_instead_of_delivering_nothing(
    monkeypatch,
):
    """An unseeded watermark used to `return`, which skipped every other config
    too, so no subscription ever received anything.
    """
    base = datetime.datetime(2026, 6, 1, 12, 0)
    notifications = [
        _notification(i, base + datetime.timedelta(minutes=i)) for i in range(3)
    ]
    unseeded = _Config(channel_id=1, last_event_date=None, subscription_name="a")
    seeded = _Config(channel_id=2, last_event_date=base, subscription_name="b")
    channel = _Channel()
    cog = _everbridge(channel, monkeypatch, notifications, [unseeded, seeded])

    await cog.get_new_notifications()

    assert unseeded.last_event_date == notifications[-1].createdAt
    # the config behind it was still processed, which the old `return` prevented
    assert len(channel.sent) == 2
    assert seeded.last_event_date == notifications[-1].createdAt


@pytest.mark.asyncio
async def test_everbridge_advances_past_a_notification_it_cannot_send(monkeypatch):
    base = datetime.datetime(2026, 6, 1, 12, 0)
    notifications = [
        _notification(i, base + datetime.timedelta(minutes=i)) for i in range(1, 4)
    ]
    config = _Config(channel_id=1, last_event_date=base, subscription_name="a")
    channel = _Channel(fail_on=2)
    cog = _everbridge(channel, monkeypatch, notifications, [config])

    await cog.get_new_notifications()

    assert len(channel.sent) == 3
    assert config.last_event_date == notifications[-1].createdAt


@pytest.mark.asyncio
async def test_everbridge_sends_oldest_first(monkeypatch):
    """The API returns newest first, which the watermark cannot cope with."""
    base = datetime.datetime(2026, 6, 1, 12, 0)
    newest_first = [
        _notification(i, base + datetime.timedelta(minutes=i)) for i in (3, 2, 1)
    ]
    config = _Config(channel_id=1, last_event_date=base, subscription_name="a")
    channel = _Channel()
    cog = _everbridge(channel, monkeypatch, newest_first, [config])

    await cog.get_new_notifications()

    assert [e.footer.text for e in channel.sent] == ["ID: 1", "ID: 2", "ID: 3"]


# ---------------------------------------------------------------------------
# redditfeed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "given,expected",
    [
        ("r/rust", "rust"),
        ("/r/rust", "rust"),
        ("/r/relationships", "relationships"),
        ("R/Rust", "rust"),
        ("rust", "rust"),
        ("  /r/rust/  ", "rust"),
        ("redscarepod", "redscarepod"),
    ],
)
def test_subreddit_names_keep_their_leading_letters(given, expected):
    """lstrip("/r/") removed a character set, not a prefix, so a subreddit
    starting with r or / lost those letters and was watched under a name that
    does not exist.
    """
    assert normalize_subreddit_name(given) == expected


class _Subreddit:
    def __init__(self, submissions):
        self._submissions = submissions

    async def new(self, limit=None):
        for submission in self._submissions:
            yield submission


def _submission(post_id, created):
    return SimpleNamespace(
        id=post_id,
        created_utc=created,
        title=f"post {post_id}",
        permalink=f"/r/test/{post_id}",
        author=SimpleNamespace(name="someone"),
        over_18=False,
        spoiler=False,
        edited=False,
        selftext="",
        removed_by_category=None,
        num_comments=0,
        score=1,
        subreddit=SimpleNamespace(display_name="test"),
    )


def _redditfeed(monkeypatch, submissions, configs, channel):
    cog = RedditFeed.__new__(RedditFeed)
    monkeypatch.setenv("REDDIT_ID", "id")
    monkeypatch.setenv("REDDIT_SECRET", "secret")
    RedditFeed.__init__(cog, _StubBot(channel))
    monkeypatch.setattr(
        cog, "reddit", SimpleNamespace(subreddit=_async_return(_Subreddit(submissions)))
    )
    monkeypatch.setattr(
        "cogs.redditfeed.redditfeed.RedditFeedConfig", _ConfigTable(configs)
    )
    monkeypatch.setattr("cogs.redditfeed.redditfeed.RedditPost", _PostTable)
    return cog


class _EmptyQuery:
    def where(self, *args):
        return self

    def tuples(self):
        return []


class _PostTable:
    """Stands in for the RedditPost model: no stored rows, no inserts."""

    post_id = "post_id"
    subreddit = "subreddit"

    @staticmethod
    def select(*args):
        return _EmptyQuery()

    @staticmethod
    def create(**kwargs):
        return None


@pytest.mark.asyncio
async def test_redditfeed_uses_each_config_own_watermark(monkeypatch):
    """The skip test used the minimum watermark across every config watching a
    subreddit, so one channel lagging behind re-posted old content to the rest.
    """
    submissions = [_submission(f"p{i}", 1000 + i) for i in range(1, 4)]
    caught_up = _Config(channel_id=1, subreddit="test", last_known_post_creation=1002)
    behind = _Config(channel_id=2, subreddit="test", last_known_post_creation=1000)
    channel = _Channel()
    cog = _redditfeed(monkeypatch, submissions, [caught_up, behind], channel)

    posted = []

    async def share_post(submission, chan):
        posted.append(submission.id)
        return SimpleNamespace(id=len(posted))

    monkeypatch.setattr(cog, "share_post", share_post)

    await cog.get_new_posts()

    # p1 and p2 go only to the config that is behind; p3 goes to both
    assert posted == ["p1", "p2", "p3", "p3"]
    assert caught_up.last_known_post_creation == 1003
    assert behind.last_known_post_creation == 1003


@pytest.mark.asyncio
async def test_redditfeed_advances_past_a_post_it_cannot_share(monkeypatch):
    submissions = [_submission(f"p{i}", 1000 + i) for i in range(1, 4)]
    config = _Config(channel_id=1, subreddit="test", last_known_post_creation=1000)
    channel = _Channel()
    cog = _redditfeed(monkeypatch, submissions, [config], channel)

    attempted = []

    async def share_post(submission, chan):
        attempted.append(submission.id)
        if submission.id == "p2":
            raise RuntimeError("image too large")
        return SimpleNamespace(id=len(attempted))

    monkeypatch.setattr(cog, "share_post", share_post)

    await cog.get_new_posts()

    assert attempted == ["p1", "p2", "p3"]
    assert config.last_known_post_creation == 1003


@pytest.mark.asyncio
async def test_redditfeed_marks_a_post_seen_even_when_sharing_failed(monkeypatch):
    """Seeding seen_ids only after a clean batch meant the next poll, ten
    seconds later, replayed the whole batch.
    """
    submissions = [_submission("p1", 1001)]
    config = _Config(channel_id=1, subreddit="test", last_known_post_creation=1000)
    cog = _redditfeed(monkeypatch, submissions, [config], _Channel())

    async def share_post(submission, chan):
        raise RuntimeError("nope")

    monkeypatch.setattr(cog, "share_post", share_post)

    await cog.get_new_posts()

    assert "p1" in cog._seen_ids["test"]
