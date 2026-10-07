"""A permission check must be the right kind for the command it decorates.

discord.py has two parallel decorator families that look interchangeable but
are not: ``commands.check``-based ones (``commands.is_owner()``,
``commands.has_permissions(...)``) only ever run for a prefix
``@commands.command``, and ``app_commands.check``-based ones
(``is_bot_owner()``, ``is_bot_owner_or_admin()``,
``app_commands.checks.has_permissions(...)``) only ever run for an app
command (``@app_commands.command`` or ``@<group>.command``). Putting the
wrong family on a command compiles and loads fine; the check is just never
consulted; the command runs unguarded for anyone.

This happened for real: admin.py's prefix `.delete`, rssfeed's `!rsstest`,
and redditfeed's `!reddittest`/`!reddittest2` all carried an app-command-only
check, and verification.py's three `/verification` subcommands and
system.py's `/block`/`/unblock` carried a prefix-only one. This is the static
regression test for that whole class, across every cog.
"""

import ast
import os

COGS_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "cogs")

# Decorator call names that only take effect on a prefix commands.command.
_PREFIX_ONLY_CHECKS = {"has_permissions", "has_guild_permissions", "is_owner", "check"}
# Decorator call names that only take effect on an app command.
_APP_ONLY_CHECKS = {"is_bot_owner", "is_bot_owner_or_admin"}


def _decorator_kind(dec: ast.expr) -> str | None:
    """Classify a single decorator as a prefix-only or app-only permission
    check, or None if it is neither (including the correctly-scoped
    counterparts, is_bot_owner_or_admin_ctx() and app_commands.checks.*).
    """
    call = dec
    if not isinstance(call, ast.Call):
        return None
    func = call.func

    # Bare name call: is_bot_owner(), is_bot_owner_or_admin()
    if isinstance(func, ast.Name) and func.id in _APP_ONLY_CHECKS:
        return "app_only"

    # Attribute call: commands.is_owner(), commands.has_permissions(...)
    if isinstance(func, ast.Attribute) and func.attr in _PREFIX_ONLY_CHECKS:
        base = func.value
        if isinstance(base, ast.Name) and base.id == "commands":
            return "prefix_only"
    return None


def _command_kind(decorators: list[ast.expr]) -> str | None:
    """Classify the command registration decorator on the same function:
    'prefix' for @commands.command/@commands.hybrid_command, 'app' for any
    other `*.command(...)` (app_commands.command, a Group's .command, etc.),
    or None if there is no command decorator at all (a plain listener, an
    error handler, a select callback, ...).
    """
    for dec in decorators:
        call = dec
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        if not isinstance(func, ast.Attribute) or func.attr != "command":
            continue
        base = func.value
        if isinstance(base, ast.Name) and base.id == "commands":
            return "prefix"
        return "app"
    return None


def test_permission_checks_match_their_command_type():
    mismatches = []
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
                decorators = node.decorator_list
                command_kind = _command_kind(decorators)
                if command_kind is None:
                    continue

                for dec in decorators:
                    check_kind = _decorator_kind(dec)
                    if check_kind is None:
                        continue
                    if check_kind == "app_only" and command_kind == "prefix":
                        rel = os.path.relpath(path, COGS_DIR).replace(os.sep, "/")
                        mismatches.append(
                            f"{rel}:{node.lineno} ({node.name}): app-command-only "
                            "check on a prefix command.command"
                        )
                    elif check_kind == "prefix_only" and command_kind == "app":
                        rel = os.path.relpath(path, COGS_DIR).replace(os.sep, "/")
                        mismatches.append(
                            f"{rel}:{node.lineno} ({node.name}): prefix-command-only "
                            "check on an app command"
                        )

    assert not mismatches, "command runs unguarded, wrong check type:\n" + "\n".join(
        mismatches
    )
