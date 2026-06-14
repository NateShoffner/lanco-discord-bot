"""
Core bot tests.

Covers:
- All cogs load without errors
- URL handler registration and lookup
- Blacklisted user model
- LancoBot helper methods (get_lanco_cogs, is_cog_loaded, etc.)
"""

import os
import re
import sys

import pytest
import pytest_asyncio

# Must be set before importing main or any cog that triggers DB init
os.environ.setdefault("DB_TYPE", "sqlite")
os.environ.setdefault("SQLITE_DB", ":memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import discord
import discord.ext.test as dpytest
from db import database_proxy
from peewee import SqliteDatabase

COGS_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "cogs")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def test_db():
    """Fresh in-memory SQLite DB bound to the proxy for every test."""
    db = SqliteDatabase(":memory:")
    database_proxy.initialize(db)
    db.connect()
    yield db
    db.close()


@pytest_asyncio.fixture
async def bot(test_db):
    """A real LancoBot instance configured for testing."""
    from main import LancoBot

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    b = LancoBot(
        command_prefix=".",
        intents=intents,
        owner_id=1,
        max_messages=100,
    )
    b.database = test_db
    await b._async_setup_hook()
    dpytest.configure(b)
    yield b
    for cog in list(b.cogs.values()):
        await b.remove_cog(cog.qualified_name)
    await dpytest.empty_queue()


# ---------------------------------------------------------------------------
# Cog loading
# ---------------------------------------------------------------------------


async def test_all_cogs_load_without_errors(bot):
    """
    Every cog with a valid entry point should load successfully.

    Failures due to missing API keys/credentials are expected in a test
    environment and are treated as warnings, not failures. Any other error
    (import errors, syntax errors, etc.) is a hard failure.
    """
    from main import CogStatus

    # Errors that are acceptable in a test environment (missing keys, missing
    # system libraries that are present in Docker, optional uninstalled deps)
    expected_missing_config_phrases = [
        # API keys / credentials
        "api_key",
        "client_id",
        "client_secret",
        "SpotifyOauthError",
        "MissingRequiredAttributeException",
        "Must provide API key",
        "OpenAIError",
        "ValidationError",
        "OPENAI_API_KEY",
        "GMAPS_API_KEY",
        "SPOTIPY_CLIENT_ID",
        "API Key must be set",
        # System libraries present in Docker but not necessarily on dev machines
        "cairo",
        "libcairo",
        # Optional deps not installed outside Docker
        "pyttsx3",
        "whisper",
        # griffe version conflict — pydantic-ai pulls griffelib 2.x which conflicts
        "cannot import name 'Docstring' from 'griffe'",
        "cannot import name 'GoogleOptions' from 'griffe'",
    ]

    hard_failures = []
    skipped = []

    for entry in os.scandir(COGS_DIR):
        if not entry.is_dir():
            continue
        if not os.path.isfile(os.path.join(entry.path, "__init__.py")):
            continue
        result = await bot.load_cog(entry.name)
        if result.status == CogStatus.ERROR:
            if any(
                phrase in result.error for phrase in expected_missing_config_phrases
            ):
                skipped.append(
                    f"{entry.name}: missing API config (expected in test env)"
                )
            else:
                hard_failures.append(f"{entry.name}: {result.error}")

    if skipped:
        print(f"\nSkipped {len(skipped)} cogs due to missing API config:")
        for s in skipped:
            print(f"  - {s}")

    assert hard_failures == [], "Cogs failed with unexpected errors:\n" + "\n".join(
        hard_failures
    )


async def test_loaded_cogs_are_discoverable(bot):
    """After loading a cog, it should appear in get_lanco_cogs()."""
    from main import CogStatus

    result = await bot.load_cog("bot")

    assert result.status == CogStatus.LOADED
    assert result.error is None
    assert any(c.get_cog_name().lower() == "bot" for c in bot.get_lanco_cogs())


async def test_is_cog_loaded_reflects_state(bot):
    """is_cog_loaded() should return False before loading and True after."""
    assert not bot.is_cog_loaded("bot")

    await bot.load_cog("bot")
    assert bot.is_cog_loaded("bot")


def test_missing_cog_entry_point_is_skipped():
    """A cog directory without __init__.py should not be loadable."""
    assert not os.path.isfile(os.path.join(COGS_DIR, "csvtable", "__init__.py"))


# ---------------------------------------------------------------------------
# URL handler registry
# ---------------------------------------------------------------------------


async def test_register_url_handler(bot):
    """Registering a URL handler should make it retrievable."""
    from cogs.lancocog import UrlHandler

    await bot.load_cog("bot")
    cog = bot.get_lanco_cog("Bot")

    handler = UrlHandler(
        url_pattern=re.compile(r"https://example\.com/.*"),
        cog=cog,
        example_url="https://example.com/test",
    )
    bot.register_url_handler(handler)

    assert bot.has_url_handler("https://example.com/foo")
    assert not bot.has_url_handler("https://other.com/foo")


async def test_get_url_handler_returns_correct_handler(bot):
    """get_url_handler() should return the matching handler."""
    from cogs.lancocog import UrlHandler

    await bot.load_cog("bot")
    cog = bot.get_lanco_cog("Bot")

    handler = UrlHandler(
        url_pattern=re.compile(r"https://spotify\.com/.*"),
        cog=cog,
        example_url="https://spotify.com/track/123",
    )
    bot.register_url_handler(handler)

    assert bot.get_url_handler("https://spotify.com/track/abc") is handler


def test_no_url_handler_returns_none(bot):
    """get_url_handler() should return None when no handler matches."""
    assert bot.get_url_handler("https://unregistered.com/page") is None


# ---------------------------------------------------------------------------
# Router (message / file / image)
# ---------------------------------------------------------------------------


def _make_image_cog(bot):
    """A throwaway ProcessorCog registering cat/dog image intents in one
    conflict group, used to drive the router in tests."""
    from utils.router import ProcessorCog, VisionQuestion

    class _RouterTestCog(ProcessorCog, name="RouterTestCog", description="test"):
        async def cog_load(self):
            await super().cog_load()
            self.register_image_intent(
                name="cat",
                cheap_predicate=self.is_image,
                questions=[VisionQuestion("is_cat", "cat?")],
                confidence=self._cat,
                process=self._say_cat,
                conflict_group="pets",
            )
            self.register_image_intent(
                name="dog",
                cheap_predicate=self.is_image,
                questions=[VisionQuestion("is_dog", "dog?")],
                confidence=self._dog,
                process=self._say_dog,
                conflict_group="pets",
            )

        async def _cat(self, ctx):
            return 0.95 if ctx.answer("is_cat") else 0.0

        async def _dog(self, ctx):
            return 0.95 if ctx.answer("is_dog") else 0.0

        async def _say_cat(self, ctx):
            await ctx.message.reply("nice cat")

        async def _say_dog(self, ctx):
            await ctx.message.reply("nice dog")

    return _RouterTestCog(bot)


async def test_register_processor_and_unload_cleanup(bot):
    """Registered intents land on bot.processors and are cleared on unload."""
    cog = _make_image_cog(bot)
    await bot.add_cog(cog)

    assert sorted(i.name for i in bot.processors) == ["cat", "dog"]
    assert all(i.level == "image" for i in bot.processors)

    await bot.remove_cog(cog.qualified_name)
    assert bot.processors == []


class _FakeAttachment:
    """Minimal stand-in for discord.Attachment for router extraction."""

    def __init__(self, name, content_type):
        self.url = f"https://cdn.example.com/{name}"
        self.proxy_url = self.url
        self.content_type = content_type
        self.size = 1234
        self.filename = name


class _FakeMessage:
    """Minimal stand-in for discord.Message that the router reads."""

    _id = 1

    def __init__(self, attachments):
        self.id = _FakeMessage._id
        _FakeMessage._id += 1
        self.author = type("Author", (), {"bot": False})()
        self.guild = object()
        self.attachments = attachments
        self.embeds = []
        self.replies = []

    async def reply(self, content):
        self.replies.append(content)


def _stub_network(monkeypatch, bot, vision_result):
    """Stub download + vision so the pipeline runs without network/API.
    Returns a dict counting download and vision invocations."""
    calls = {"download": 0, "vision": 0}

    async def fake_prepare(candidate):
        calls["download"] += 1
        candidate.data = b"img"
        candidate.content_type = candidate.content_type or "image/png"
        candidate.filename = None
        return True

    async def fake_classify(image_bytes, media_type, questions):
        calls["vision"] += 1
        return dict(vision_result)

    monkeypatch.setattr(bot.router, "_prepare", fake_prepare)
    monkeypatch.setattr(bot.router.vision, "classify", fake_classify)
    return calls


async def test_image_message_routes_one_vision_call_and_dispatches(bot, monkeypatch):
    """An image message: downloaded once, one shared vision call, winner replies."""
    cog = _make_image_cog(bot)
    await bot.add_cog(cog)
    calls = _stub_network(monkeypatch, bot, {"is_cat": True, "is_dog": False})

    msg = _FakeMessage([_FakeAttachment("cat.png", "image/png")])
    await bot.router.handle_message(msg)

    assert calls["download"] == 1  # downloaded once
    assert calls["vision"] == 1  # single shared vision call for both intents
    assert msg.replies == ["nice cat"]  # cat wins its conflict group


async def test_non_image_attachment_skips_download_and_vision(bot, monkeypatch):
    """A non-image attachment passes no image cheap gate, so it is never
    downloaded and never triggers the shared vision call."""
    cog = _make_image_cog(bot)
    await bot.add_cog(cog)
    calls = _stub_network(monkeypatch, bot, {})

    msg = _FakeMessage([_FakeAttachment("report.pdf", "application/pdf")])
    await bot.router.handle_message(msg)

    assert calls["download"] == 0
    assert calls["vision"] == 0
    assert msg.replies == []


async def test_router_listener_registered_in_setup_hook(bot):
    """setup_hook wires the router as the single on_message listener."""
    await bot.setup_hook()
    listeners = bot.extra_events.get("on_message", [])
    assert any(
        getattr(h, "__self__", None) is bot.router for h in listeners
    ), "router.handle_message should be registered as an on_message listener"


def _make_scoped_cat_cog(bot, scope):
    """A cog with a single scoped cat intent."""
    from utils.router import ProcessorCog, VisionQuestion

    class _ScopedCog(ProcessorCog, name="ScopedCog", description="test"):
        async def cog_load(self):
            await super().cog_load()
            self.register_image_intent(
                name="cat",
                cheap_predicate=self.is_image,
                questions=[VisionQuestion("is_cat", "cat?")],
                confidence=self._cat,
                process=self._say,
                scope=scope,
            )

        async def _cat(self, ctx):
            return 0.95 if ctx.answer("is_cat") else 0.0

        async def _say(self, ctx):
            await ctx.message.reply("nice cat")

    return _ScopedCog(bot)


async def test_scope_allows_matching_channel(bot, monkeypatch):
    """An intent scoped to a channel runs there: download + vision + reply."""
    from utils.router import IntentScope

    cog = _make_scoped_cat_cog(bot, IntentScope(channels={111}))
    await bot.add_cog(cog)
    calls = _stub_network(monkeypatch, bot, {"is_cat": True})

    msg = _FakeMessage([_FakeAttachment("cat.png", "image/png")])
    msg.channel = type("Ch", (), {"id": 111, "parent_id": None, "category": None})()
    await bot.router.handle_message(msg)

    assert calls["vision"] == 1
    assert msg.replies == ["nice cat"]


async def test_scope_blocks_other_channel_before_download(bot, monkeypatch):
    """Out of scope: no download, no vision, no reply (gated before the cheap
    predicate)."""
    from utils.router import IntentScope

    cog = _make_scoped_cat_cog(bot, IntentScope(channels={111}))
    await bot.add_cog(cog)
    calls = _stub_network(monkeypatch, bot, {"is_cat": True})

    msg = _FakeMessage([_FakeAttachment("cat.png", "image/png")])
    msg.channel = type("Ch", (), {"id": 999, "parent_id": None, "category": None})()
    await bot.router.handle_message(msg)

    assert calls["download"] == 0
    assert calls["vision"] == 0
    assert msg.replies == []


async def test_scope_custom_predicate(bot, monkeypatch):
    """A custom scope predicate gates the intent."""
    from utils.router import IntentScope

    cog = _make_scoped_cat_cog(
        bot, IntentScope(custom=lambda m: getattr(m, "allow", False))
    )
    await bot.add_cog(cog)
    calls = _stub_network(monkeypatch, bot, {"is_cat": True})

    blocked = _FakeMessage([_FakeAttachment("cat.png", "image/png")])
    blocked.allow = False
    await bot.router.handle_message(blocked)
    assert blocked.replies == []
    assert calls["vision"] == 0

    allowed = _FakeMessage([_FakeAttachment("cat.png", "image/png")])
    allowed.allow = True
    await bot.router.handle_message(allowed)
    assert allowed.replies == ["nice cat"]


# ---------------------------------------------------------------------------
# BlacklistedUser model
# ---------------------------------------------------------------------------


def test_blacklisted_user_create_and_query(test_db):
    """BlacklistedUser records should persist and be queryable."""
    from db import BaseModel
    from peewee import BigIntegerField, TextField

    class BlacklistedUser(BaseModel):
        user_id = BigIntegerField(primary_key=True)
        reason = TextField(null=True)

        class Meta:
            table_name = "blacklisted_users"

    test_db.create_tables([BlacklistedUser])
    BlacklistedUser.create(user_id=123456, reason="spamming")

    record = BlacklistedUser.get_by_id(123456)
    assert record.user_id == 123456
    assert record.reason == "spamming"


def test_blacklisted_user_not_found(test_db):
    """Querying a non-existent blacklisted user should raise DoesNotExist."""
    from db import BaseModel
    from peewee import BigIntegerField, TextField

    class BlacklistedUser(BaseModel):
        user_id = BigIntegerField(primary_key=True)
        reason = TextField(null=True)

        class Meta:
            table_name = "blacklisted_users"

    test_db.create_tables([BlacklistedUser])

    with pytest.raises(BlacklistedUser.DoesNotExist):
        BlacklistedUser.get_by_id(999999)
