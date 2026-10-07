"""An owner-gated command that posts a View must post it ephemerally.

@is_bot_owner()/@is_bot_owner_or_admin() only gates the slash command
invocation itself; it is never re-checked when a component on a View the
command posts is clicked. A non-ephemeral message's components are visible,
and so clickable, by anyone who can see the channel - not just the command's
caller. /geoguesser populate and /incidents setclient both posted a public
Select this way: the slash command was owner-only, but the Select behind it
(100 paid Google Maps lookups; changing the global incident feed client) was
not. Ephemeral is what actually restricts the followup, matching
/geoguesser wipe's equivalent Select, which already got this right.

This is the static regression test for that class of bug, across every cog.
"""

import ast
import os

COGS_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "cogs")

_OWNER_CHECKS = {"is_bot_owner", "is_bot_owner_or_admin"}


def _is_owner_check(dec: ast.expr) -> bool:
    return (
        isinstance(dec, ast.Call)
        and isinstance(dec.func, ast.Name)
        and dec.func.id in _OWNER_CHECKS
    )


def _is_ephemeral_true(keyword: ast.keyword) -> bool:
    return keyword.arg == "ephemeral" and (
        isinstance(keyword.value, ast.Constant) and keyword.value.value is True
    )


def _sends_a_non_ephemeral_view(func: ast.AST) -> list[int]:
    """Line numbers of send_message(view=..., ...) calls in this function's
    body that do not also pass ephemeral=True.
    """
    offenders = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        if not (isinstance(callee, ast.Attribute) and callee.attr == "send_message"):
            continue
        has_view = any(kw.arg == "view" for kw in node.keywords)
        if not has_view:
            continue
        if any(_is_ephemeral_true(kw) for kw in node.keywords):
            continue
        offenders.append(node.lineno)
    return offenders


def test_owner_gated_commands_post_views_ephemerally():
    offenders = []
    for root, _dirs, files in os.walk(COGS_DIR):
        if "__pycache__" in root:
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(root, fn)
            src = open(path, encoding="utf-8", errors="replace").read()
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not any(_is_owner_check(dec) for dec in node.decorator_list):
                    continue
                for lineno in _sends_a_non_ephemeral_view(node):
                    rel = os.path.relpath(path, COGS_DIR).replace(os.sep, "/")
                    offenders.append(f"{rel}:{lineno} ({node.name})")

    assert not offenders, (
        "owner-gated command posts a View without ephemeral=True, so anyone "
        "who can see the channel can use it: " + ", ".join(offenders)
    )
