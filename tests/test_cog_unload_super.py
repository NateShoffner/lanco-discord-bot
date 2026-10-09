"""A cog that overrides cog_unload must still call LancoCog's.

`LancoCog.cog_unload` is where a cog's context menus come off the command
tree, its URL handlers and router intents come out of the bot's registries, and
its tracked tasks and `start_loop` loops get cancelled. An override that skips
`super()` skips all of that: on reload the old cog's menus stay registered, its
intents keep being dispatched to a dead instance, and its loops keep running
alongside the new ones.

Worse, a *synchronous* override of an async method does not just skip the
cleanup, it is a different signature. discord.py tolerates it, so nothing
complains at load time and nothing complains at unload time either.

Twelve cogs had this. They were all harmless by luck (none of them registered a
context menu or an intent), which is exactly why it needed a test rather than a
comment.
"""

import ast
import os

COGS_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "cogs")
BASE_CLASS_FILE = "lancocog.py"


def _overrides(path: str):
    """Yield (class_name, node) for every cog_unload defined in the file."""
    tree = ast.parse(open(path, encoding="utf-8").read())
    for cls in ast.walk(tree):
        if not isinstance(cls, ast.ClassDef):
            continue
        for node in cls.body:
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "cog_unload"
            ):
                yield cls.name, node


def _calls_super_cog_unload(node: ast.AST) -> bool:
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call):
            continue
        func = inner.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "cog_unload"
            and isinstance(func.value, ast.Call)
            and isinstance(func.value.func, ast.Name)
            and func.value.func.id == "super"
        ):
            return True
    return False


def _cog_files():
    for root, _dirs, files in os.walk(COGS_DIR):
        if "__pycache__" in root:
            continue
        for fn in files:
            if fn.endswith(".py") and fn != BASE_CLASS_FILE:
                yield os.path.join(root, fn)


def test_every_cog_unload_override_calls_super():
    offenders = []
    for path in _cog_files():
        rel = os.path.relpath(path, COGS_DIR).replace(os.sep, "/")
        for cls_name, node in _overrides(path):
            if not _calls_super_cog_unload(node):
                offenders.append(
                    f"{rel}:{node.lineno} ({cls_name}) skips LancoCog's cleanup"
                )
    assert not offenders, "\n".join(offenders)


def test_every_cog_unload_override_is_a_coroutine():
    """LancoCog.cog_unload is async, so a sync override cannot await it."""
    offenders = []
    for path in _cog_files():
        rel = os.path.relpath(path, COGS_DIR).replace(os.sep, "/")
        for cls_name, node in _overrides(path):
            if not isinstance(node, ast.AsyncFunctionDef):
                offenders.append(
                    f"{rel}:{node.lineno} ({cls_name}) is def, not async def"
                )
    assert not offenders, "\n".join(offenders)


def test_the_scan_actually_finds_the_overrides():
    """Guards both tests above against silently matching nothing."""
    found = sum(1 for path in _cog_files() for _ in _overrides(path))
    assert found >= 12, f"only found {found} cog_unload overrides"
