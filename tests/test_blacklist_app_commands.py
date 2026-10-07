"""The blacklist must cover app commands, not just prefix commands.

BlacklistedUser was only ever enforced by global_block_check, which is
registered via bot.check and therefore only runs for prefix commands; slash
commands and context menus skip it entirely. InstrumentedCommandTree.
interaction_check() is the app-command counterpart, mirrored on the tree the
same way global_block_check is mirrored on the bot.
"""

import os
import sys

os.environ.setdefault("BOT_ENV", "test")
os.environ.setdefault("DB_TYPE", "sqlite")
os.environ.setdefault("SQLITE_DB", ":memory:")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import pytest

from tests.test_bot import test_db  # noqa: F401  (fixture)

pytestmark = pytest.mark.asyncio


class _FakeUser:
    def __init__(self, user_id: int):
        self.id = user_id


class _FakeInteraction:
    """Only the attribute interaction_check() actually reads."""

    def __init__(self, user_id: int):
        self.user = _FakeUser(user_id)


async def test_interaction_check_blocks_blacklisted_user(test_db):
    from main import BlacklistedUser, InstrumentedCommandTree

    test_db.create_tables([BlacklistedUser])
    BlacklistedUser.create(user_id=555, reason="spam")

    # self is never touched in the body, so this can be called unbound rather
    # than standing up a full CommandTree (which refuses to coexist with the
    # bot's own tree on one client).
    allowed = await InstrumentedCommandTree.interaction_check(
        None, _FakeInteraction(555)
    )
    assert allowed is False


async def test_interaction_check_allows_other_users(test_db):
    from main import BlacklistedUser, InstrumentedCommandTree

    test_db.create_tables([BlacklistedUser])
    BlacklistedUser.create(user_id=555, reason="spam")

    allowed = await InstrumentedCommandTree.interaction_check(
        None, _FakeInteraction(999)
    )
    assert allowed is True
