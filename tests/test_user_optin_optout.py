"""/optin must not be able to undo an owner-imposed /block.

Both commands shared one BlacklistedUser row with no way to tell who created
it or why, so /optin deleted the row unconditionally - a user could always
opt themselves back in even after the owner explicitly blocked them. The fix
distinguishes a self-service /optout row (no reason) from an owner /block
row (always has one) and refuses to let /optin touch the latter.
"""

from types import SimpleNamespace

import pytest
from cogs.user.user import UserCog
from models_core import BlacklistedUser

from tests.test_bot import test_db  # noqa: F401  (fixture)

pytestmark = pytest.mark.asyncio

USER_ID = 42


class _FakeResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, content=None, *, ephemeral=False):
        self.messages.append(content)


def make_interaction(user_id=USER_ID):
    return SimpleNamespace(user=SimpleNamespace(id=user_id), response=_FakeResponse())


@pytest.fixture(autouse=True)
def tables(test_db):
    test_db.create_tables([BlacklistedUser])


@pytest.fixture
def cog(test_db):
    return UserCog(SimpleNamespace(database=test_db))


async def test_optin_refuses_an_owner_block(cog):
    BlacklistedUser.create(user_id=USER_ID, reason="spamming")
    interaction = make_interaction()

    await UserCog.optin.callback(cog, interaction)

    assert BlacklistedUser.get_or_none(user_id=USER_ID) is not None
    assert "blocked by the bot owner" in interaction.response.messages[0]


async def test_optin_allows_undoing_a_self_optout(cog):
    await UserCog.optout.callback(cog, make_interaction())
    assert BlacklistedUser.get_or_none(user_id=USER_ID) is not None

    await UserCog.optin.callback(cog, make_interaction())

    assert BlacklistedUser.get_or_none(user_id=USER_ID) is None
