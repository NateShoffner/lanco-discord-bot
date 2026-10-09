"""Commands that cost money per invocation must carry a cooldown.

Each of these spends on every call: an LLM or vision request, a third-party
API hit, or in `sleepcheck`'s case up to 500 messages of history and one vision
call per attachment found. With no cooldown, one person holding a key down runs
up the bill, and in `sleepcheck`'s case does it for the whole guild.

The table below is the inventory, checked statically, so removing a decorator
or renaming a command out from under one fails here rather than on the invoice.
Cooldowns already present before this (TechLanc's) are not listed; this is the
set that had none.
"""

import ast
import os

import discord
import pytest
from discord import app_commands

APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")

#: module path -> callables that must carry a cooldown decorator.
REQUIRED_COOLDOWNS = {
    "cogs/hotdog/hotdog.py": {"hotdog", "ctx_menu"},
    "cogs/describe/describe.py": {"ctx_menu"},
    "cogs/AIDetection/AIDetection.py": {"ctx_menu"},
    "cogs/summarize/summarize.py": {"topic", "vibecheck", "eli5", "chime"},
    "cogs/tracemoe/tracemoe.py": {"tracemoe"},
    "cogs/wolframalpha/wolframalpha.py": {"calc"},
    "cogs/sleepcheck/sleepcheck.py": {"today"},
}


def _is_cooldown_decorator(dec: ast.expr) -> bool:
    """True for commands.cooldown(...) or app_commands.checks.cooldown(...)."""
    return (
        isinstance(dec, ast.Call)
        and isinstance(dec.func, ast.Attribute)
        and dec.func.attr == "cooldown"
    )


def _functions(path: str) -> dict:
    tree = ast.parse(open(path, encoding="utf-8").read())
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.setdefault(node.name, node)
    return found


@pytest.mark.parametrize("rel", sorted(REQUIRED_COOLDOWNS))
def test_paid_commands_carry_a_cooldown(rel):
    path = os.path.join(APP_DIR, *rel.split("/"))
    functions = _functions(path)

    for name in sorted(REQUIRED_COOLDOWNS[rel]):
        assert name in functions, f"{rel}: {name} is gone, did it get renamed?"
        node = functions[name]
        assert any(
            _is_cooldown_decorator(d) for d in node.decorator_list
        ), f"{rel}:{node.lineno} ({name}) spends money with no cooldown"


# ---------------------------------------------------------------------------
# A cooldown on a context menu is wired up differently, so check it for real.
# ---------------------------------------------------------------------------


class _StubTree:
    def __init__(self):
        self.commands = []

    def add_command(self, command):
        self.commands.append(command)


class _StubBot:
    def __init__(self):
        self.tree = _StubTree()


CONTEXT_MENU_COGS = [
    ("cogs.hotdog.hotdog", "HotDog"),
    ("cogs.describe.describe", "Describe"),
    ("cogs.AIDetection.AIDetection", "AIDetection"),
]


@pytest.fixture
def cog_factory(monkeypatch):
    """Build one of the cogs above. pydantic_ai resolves the model eagerly in
    Agent(), which refuses to construct without a key.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def build(module_name, class_name):
        module = __import__(module_name, fromlist=[class_name])
        return getattr(module, class_name)(_StubBot())

    return build


@pytest.mark.parametrize("module_name,class_name", CONTEXT_MENU_COGS)
def test_context_menu_picks_up_the_cooldown_check(cog_factory, module_name, class_name):
    """app_commands.checks.cooldown stashes its predicate on the function, and
    ContextMenu reads it from there when register_context_menu builds it.
    """
    cog = cog_factory(module_name, class_name)

    menus = [
        c for c in cog.bot.tree.commands if isinstance(c, app_commands.ContextMenu)
    ]
    assert menus, f"{class_name} registered no context menu"
    for menu in menus:
        assert menu.checks, f"{class_name}'s {menu.name!r} menu has no cooldown check"


class _FakeResponse:
    def __init__(self):
        self.sent = []

    async def send_message(self, content=None, **kwargs):
        self.sent.append((content, kwargs))


class _FakeInteraction:
    def __init__(self):
        self.response = _FakeResponse()

    async def edit_original_response(self, **kwargs):
        raise AssertionError("nothing was sent yet, so there is nothing to edit")


@pytest.mark.parametrize("module_name,class_name", CONTEXT_MENU_COGS)
@pytest.mark.asyncio
async def test_cooldown_errback_replies_instead_of_editing(
    cog_factory, module_name, class_name
):
    """The errback's edit_original_response only works once something has been
    sent, which on a cooldown hit it has not.
    """
    cog = cog_factory(module_name, class_name)

    interaction = _FakeInteraction()
    error = app_commands.CommandOnCooldown(discord.app_commands.Cooldown(1, 30.0), 12.0)

    await cog.ctx_menu_error(interaction, error)

    assert interaction.response.sent, "user was told nothing about the cooldown"
    content, kwargs = interaction.response.sent[0]
    assert "cooldown" in content.lower()
    assert kwargs.get("ephemeral") is True
