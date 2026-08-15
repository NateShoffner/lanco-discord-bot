"""Cog on_message listeners must survive a direct message.

`message.guild` is None in a DM and in a group DM. A listener that dereferences
it without checking raises AttributeError on every DM, which surfaces as an
unhandled error in on_error and a report to APM.

Two complementary checks:

- a runtime one, dispatching a DM-shaped message at every listener that loads
- a static one, covering the cogs that cannot be imported without their optional
  system libraries (filefixer needs cairo, transcribe needs whisper)
"""

import ast
import os
import re
import types

import discord
import pytest

from tests.test_bot import bot, test_db  # noqa: F401  (fixtures)

COGS_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "cogs")

pytestmark = pytest.mark.asyncio

# Any of these in a listener body counts as guarding the DM case. The trailing
# lookahead on the bare form keeps `if message.guild.id == x` from being read as
# a guard, while still matching the ternary form `x if message.guild else y`.
GUARD_FORMS = (
    r"message\.guild\s+is\s+None",
    r"message\.guild\s+is\s+not\s+None",
    r"not\s+message\.guild(?![.\w])",
    r"if\s+message\.guild(?![.\w])",
)


class _Author:
    bot = False
    id = 999
    display_name = "someone"

    def __str__(self):
        return "someone"


class _Attachment:
    filename = "x.heic"
    url = "http://example.invalid/x.heic"
    content_type = "image/heic"
    size = 10


class _DMChannel(discord.DMChannel):
    def __init__(self):
        self.id = 4242

    async def send(self, *a, **k):
        return None

    async def fetch_message(self, *a, **k):
        return None

    async def typing(self):
        return None


class _DM:
    """A message shaped like a DM: guild is None."""

    def __init__(self, content="", attachments=()):
        self.author = _Author()
        self.guild = None
        self.channel = _DMChannel()
        self.content = content
        self.attachments = list(attachments)
        self.id = 1
        self.embeds = []

    async def add_reaction(self, *a, **k):
        return None

    async def reply(self, *a, **k):
        return None

    async def delete(self, *a, **k):
        return None


# Content shaped to reach the deeper branches of the URL and attachment cogs
PAYLOADS = (
    lambda: _DM("hello there"),
    lambda: _DM("look http://example.invalid/page"),
    lambda: _DM("https://open.spotify.com/track/abc123"),
    lambda: _DM("https://truthsocial.com/@someone/posts/123456"),
    lambda: _DM("file", [_Attachment()]),
)


async def test_no_listener_raises_on_a_dm(bot):
    for entry in os.scandir(COGS_DIR):
        if entry.is_dir() and os.path.isfile(os.path.join(entry.path, "__init__.py")):
            await bot.load_cog(entry.name)

    raised = {}
    exercised = 0
    for cog in bot.cogs.values():
        # get_listeners() rather than looking up an `on_message` attribute:
        # listeners can be registered under any function name via
        # @commands.Cog.listener("on_message"), and facebookembed has three.
        for event_name, listener in cog.get_listeners():
            if event_name != "on_message":
                continue
            exercised += 1
            label = f"{cog.qualified_name}.{listener.__name__}"
            for make in PAYLOADS:
                try:
                    await listener(make())
                except AttributeError as e:
                    # The failure this test exists for: touching a None guild
                    if "guild" in str(e) or "NoneType" in str(e):
                        raised.setdefault(label, str(e))
                except Exception:
                    # Anything else is the stub message being incomplete, not a
                    # DM-handling bug
                    pass

    assert exercised, "no on_message listeners were exercised"
    assert not raised, f"listeners raising on a DM: {raised}"


def _dereferences_guild(func: ast.AST) -> bool:
    """True if the body reads an attribute off message.guild.

    Passing `message.guild` along as a value is fine, since the callee can take
    None. `message.guild.id` is what raises in a DM.
    """
    for node in ast.walk(func):
        if not isinstance(node, ast.Attribute):
            continue
        inner = node.value
        if (
            isinstance(inner, ast.Attribute)
            and inner.attr == "guild"
            and isinstance(inner.value, ast.Name)
            and inner.value.id == "message"
        ):
            return True
    return False


def test_guild_referencing_listeners_guard_against_dms():
    """Static counterpart, so cogs that cannot import here are still covered."""
    offenders = []
    for root, _dirs, files in os.walk(COGS_DIR):
        if "__pycache__" in root:
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(root, fn)
            src = open(path, encoding="utf-8", errors="replace").read()
            if "async def on_message" not in src:
                continue
            lines = src.split("\n")
            for node in ast.walk(ast.parse(src)):
                if not (
                    isinstance(node, ast.AsyncFunctionDef) and node.name == "on_message"
                ):
                    continue
                if not _dereferences_guild(node):
                    continue
                body = "\n".join(lines[node.lineno - 1 : node.end_lineno])
                if not any(re.search(form, body) for form in GUARD_FORMS):
                    rel = os.path.relpath(path, COGS_DIR).replace(os.sep, "/")
                    offenders.append(f"{rel}:{node.lineno}")

    assert not offenders, (
        "on_message listeners referencing message.guild without a DM guard: "
        + ", ".join(offenders)
    )
