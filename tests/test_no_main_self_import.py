"""A cog must never import main.py at runtime.

The process runs main.py as __main__ (python app/main.py) or app.main
(poetry's entrypoints), never as a module named "main". `import main` or
`from main import X` from inside a cog therefore does not reuse the running
instance - it re-executes the entire module under a second name, building a
second LancoBot, rebinding the database proxy to a second connection, and
clearing/rebuilding the root log handlers. This happened for real: several
cogs did it to reach BlacklistedUser or the LancoBot type for a hint.

models_core.py exists so a model can be imported without importing main.py;
a TYPE_CHECKING-guarded import (never executed) is the escape hatch for a
type hint that still needs main.LancoBot specifically.

This is the static regression test for that whole class, across every file
under app/, not just the cogs that were affected.
"""

import ast
import os

APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")
_EXEMPT_FILES = {"main.py", "run.py"}


def _type_checking_line_ranges(tree: ast.AST) -> list[tuple[int, int]]:
    """Line ranges covered by an `if TYPE_CHECKING:` block, where an import
    is never executed at runtime.
    """
    ranges = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        is_type_checking = (
            isinstance(test, ast.Name) and test.id == "TYPE_CHECKING"
        ) or (isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")
        if is_type_checking:
            ranges.append((node.lineno, node.end_lineno))
    return ranges


def _imports_main(node: ast.AST) -> bool:
    if isinstance(node, ast.Import):
        return any(alias.name == "main" for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return node.module == "main"
    return False


def test_no_file_imports_main_outside_type_checking():
    offenders = []
    for root, _dirs, files in os.walk(APP_DIR):
        if "__pycache__" in root:
            continue
        for fn in files:
            if not fn.endswith(".py") or fn in _EXEMPT_FILES:
                continue
            path = os.path.join(root, fn)
            src = open(path, encoding="utf-8", errors="replace").read()
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue

            exempt_ranges = _type_checking_line_ranges(tree)
            for node in ast.walk(tree):
                if not _imports_main(node):
                    continue
                if any(start <= node.lineno <= end for start, end in exempt_ranges):
                    continue
                rel = os.path.relpath(path, APP_DIR).replace(os.sep, "/")
                offenders.append(f"{rel}:{node.lineno}")

    assert not offenders, (
        "these files import main.py at runtime, which re-executes it as a "
        "second module instead of reusing the running bot (move the model "
        "to models_core.py, or guard a type-only import with "
        "`if TYPE_CHECKING:`): " + ", ".join(offenders)
    )
