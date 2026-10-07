"""The round-results map is attached as a file, not linked by its request URL.

The Static Maps URL carries the API key as a query parameter, so
build_results_embed fetches the image server-side and attaches it, the same
pattern build_round_embed already uses for the Street View photo. The
outgoing request is expected to carry the key; nothing sent to Discord should.
"""

import logging
from types import SimpleNamespace

import aiohttp
import pytest
from cogs.geoguesser.geoguesser import GeoGuesser
from cogs.geoguesser.models import Coordinates, GeoGuesserLocation, GuessResult, Round

pytestmark = pytest.mark.asyncio

API_KEY = "super-secret-maps-key"


class _FakeResponse:
    def __init__(self, status=200, body=b"\x89PNG\r\n\x1a\n"):
        self.status = status
        self._body = body

    async def read(self):
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeAiohttpSession:
    """Stands in for aiohttp.ClientSession(); records the URL it was asked
    to fetch so the test can confirm which URL carries the key (the outgoing
    request, which is expected to) versus what ends up in the embed (which
    must not).
    """

    def __init__(self, response):
        self._response = response
        self.requested_url = None

    def get(self, url):
        self.requested_url = url
        return self._response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def cog(monkeypatch):
    monkeypatch.setenv("GMAPS_API_KEY", API_KEY)
    # build_results_embed only touches self.logger and self.build_leaderboard
    # (inherited from RoundGameCog), so a real GeoGuesser - which needs a
    # live bot, Google client, cached locations, etc. to construct - is
    # unnecessary here.
    instance = object.__new__(GeoGuesser)
    instance.logger = logging.getLogger("test-geoguesser")
    return instance


def make_session(guess_coords=None):
    location = GeoGuesserLocation(
        initial_location=Coordinates(40.0, -76.0),
        road_coords=Coordinates(40.001, -76.001),
        label="Test & Main St",
    )
    round_ = Round(number=0, location=location)
    if guess_coords is not None:
        round_.add_guess(
            111, GuessResult(distance=123.4, score=50.0, guess_coords=guess_coords)
        )

    guild = SimpleNamespace(
        get_member=lambda uid: SimpleNamespace(display_name=f"user-{uid}")
    )
    channel = SimpleNamespace(guild=guild)
    mode = SimpleNamespace(score_radius=2000)
    return SimpleNamespace(
        rounds=[round_],
        channel=channel,
        mode=mode,
        members={},
        get_current_round=lambda: round_,
    )


async def test_results_embed_attaches_the_map_instead_of_linking_it(cog, monkeypatch):
    fake_session = _FakeAiohttpSession(_FakeResponse())
    monkeypatch.setattr(aiohttp, "ClientSession", lambda *a, **k: fake_session)

    session = make_session(guess_coords=Coordinates(40.002, -76.002))
    embed, files = await cog.build_results_embed(session, next_round_time=None)

    # The outgoing request to Google is expected to carry the key...
    assert API_KEY in fake_session.requested_url
    # ...but nothing sent to Discord should.
    assert embed.image.url == "attachment://results_map.png"
    assert API_KEY not in embed.image.url
    for field in embed.fields:
        assert API_KEY not in (field.value or "")
    assert len(files) == 1
    assert files[0].filename == "results_map.png"


async def test_results_embed_has_no_image_when_the_map_request_fails(cog, monkeypatch):
    fake_session = _FakeAiohttpSession(_FakeResponse(status=403))
    monkeypatch.setattr(aiohttp, "ClientSession", lambda *a, **k: fake_session)

    session = make_session()
    embed, files = await cog.build_results_embed(session, next_round_time=None)

    assert files == []
    assert embed.image.url is None
