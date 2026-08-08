import os
import sys

# Ensure test env vars are set before any app imports trigger DB init
os.environ.setdefault("DB_TYPE", "sqlite")
os.environ.setdefault("SQLITE_DB", ":memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import pytest
import pytest_asyncio
from db import database_proxy, discover_model_modules
from peewee import SqliteDatabase
from tortoise.contrib.test import tortoise_test_context


@pytest.fixture(autouse=True)
def test_db():
    """Fresh in-memory SQLite DB bound to the proxy for every test.

    Peewee side. Stays autouse (and stays put) until every model has been
    ported to Tortoise -- see the migration plan for issue #149. Both ORMs are
    live at once during the cutover, which is safe: they open independent
    connections to the same database.
    """
    db = SqliteDatabase(":memory:")
    database_proxy.initialize(db)
    db.connect()
    yield db
    db.close()


@pytest_asyncio.fixture
async def tortoise_db():
    """Fresh in-memory Tortoise DB with all ported models, per test.

    Deliberately NOT autouse: it is an async fixture, and the suite still has
    sync tests that would receive an un-awaited async generator. Tests (and the
    `bot` fixture) opt in by requesting it.

    use_tz=False mirrors production: Peewee wrote naive datetimes, so every
    existing row is naive and Tortoise must not start writing aware ones.
    """
    async with tortoise_test_context(discover_model_modules(), use_tz=False) as ctx:
        yield ctx
