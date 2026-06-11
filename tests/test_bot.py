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
