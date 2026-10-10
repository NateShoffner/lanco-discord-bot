"""A background loop must survive a bad iteration and wait for the gateway.

`tasks.loop` stops permanently at the first unhandled exception. One guild's
unreachable channel, malformed feed entry, or expired API key therefore
silently stopped reminders, scheduled posts, incident alerts and birthday
announcements for *every* guild, until someone reloaded the cog. Nothing
reported it.

Separately, a loop started from `cog_load` runs before the gateway connects,
where `get_channel` returns None for every channel. `remindme` marked those
reminders issued anyway, so anything due at startup was consumed without being
delivered.

`LancoCog.start_loop` fixes both, and the static check at the bottom is what
keeps the next loop from being added the old way.
"""

import ast
import asyncio
import os

import pytest
from cogs.lancocog import LancoCog
from discord.ext import tasks

COGS_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "cogs")


class _StubBot:
    def __init__(self):
        self.ready = asyncio.Event()
        self.waited = 0

    async def wait_until_ready(self):
        self.waited += 1
        await self.ready.wait()


class _LoopCog(LancoCog, name="LoopCog"):
    """A cog with a loop whose body is driven by the test."""

    def __init__(self, bot):
        super().__init__(bot)
        self.iterations = 0
        self.fail_until = 0
        self.ran = asyncio.Event()

    @tasks.loop(seconds=0.01)
    async def ticker(self):
        self.iterations += 1
        self.ran.set()
        if self.iterations <= self.fail_until:
            raise RuntimeError(f"iteration {self.iterations} is bad")


async def _wait_for(predicate, timeout=5.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.01)
    return False


@pytest.fixture
def cog():
    bot = _StubBot()
    c = _LoopCog(bot)
    yield c
    c.ticker.cancel()


@pytest.mark.asyncio
async def test_the_loop_does_not_start_before_the_bot_is_ready(cog):
    cog.start_loop(cog.ticker)

    assert not await _wait_for(lambda: cog.iterations > 0, timeout=0.3)
    assert cog.bot.waited == 1, "the loop never awaited wait_until_ready"

    cog.bot.ready.set()
    assert await _wait_for(lambda: cog.iterations > 0)


@pytest.mark.asyncio
async def test_a_raising_iteration_does_not_kill_the_loop(cog):
    cog.fail_until = 3
    cog.bot.ready.set()
    cog.start_loop(cog.ticker)

    assert await _wait_for(lambda: cog.iterations >= 6)
    assert not cog.ticker.is_being_cancelled()
    assert cog.ticker.failed() is False, "loop gave up after an exception"


@pytest.mark.asyncio
async def test_the_failure_is_logged_with_a_traceback(cog, caplog):
    cog.fail_until = 1
    cog.bot.ready.set()
    cog.start_loop(cog.ticker)

    assert await _wait_for(lambda: cog.iterations >= 2)
    assert any(
        r.levelname == "ERROR" and r.exc_info for r in caplog.records
    ), "a swallowed exception with no traceback is worse than a dead loop"


@pytest.mark.asyncio
async def test_wait_for_ready_can_be_opted_out_of(cog):
    """For a loop that touches no Discord state, e.g. refreshing a cache."""
    cog.start_loop(cog.ticker, wait_for_ready=False)

    assert await _wait_for(lambda: cog.iterations > 0)
    assert cog.bot.waited == 0


@pytest.mark.asyncio
async def test_unload_cancels_the_loop(cog):
    cog.bot.ready.set()
    cog.start_loop(cog.ticker)
    assert await _wait_for(lambda: cog.iterations > 0)

    cog.bot.url_handlers = []
    cog.bot.processors = []
    await cog.cog_unload()

    # cancel() only takes effect once the task gets to observe it
    assert await _wait_for(lambda: not cog.ticker.is_running())


@pytest.mark.asyncio
async def test_an_existing_before_loop_hook_still_runs(cog):
    """start_loop composes with a cog's own hook rather than replacing it."""
    called = []

    async def own_hook(*_args):
        called.append(True)

    cog.ticker.before_loop(own_hook)
    cog.bot.ready.set()
    cog.start_loop(cog.ticker)

    assert await _wait_for(lambda: cog.iterations > 0)
    assert called, "the cog's own before_loop hook was dropped"


# ---------------------------------------------------------------------------
# Static: no cog may start a loop the unguarded way.
# ---------------------------------------------------------------------------


def _loop_attribute_names(tree: ast.AST) -> set[str]:
    """Names of functions in this module decorated with @tasks.loop(...)."""
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if (
                isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Attribute)
                and dec.func.attr == "loop"
            ):
                names.add(node.name)
    return names


def test_every_tasks_loop_is_started_through_start_loop():
    offenders = []
    for root, _dirs, files in os.walk(COGS_DIR):
        if "__pycache__" in root:
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(root, fn)
            tree = ast.parse(open(path, encoding="utf-8").read())
            loops = _loop_attribute_names(tree)
            if not loops:
                continue

            for node in ast.walk(tree):
                # self.<loop>.start() rather than self.start_loop(self.<loop>)
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not isinstance(func, ast.Attribute) or func.attr != "start":
                    continue
                target = func.value
                if isinstance(target, ast.Attribute) and target.attr in loops:
                    rel = os.path.relpath(path, COGS_DIR).replace(os.sep, "/")
                    offenders.append(f"{rel}:{node.lineno} ({target.attr})")

    assert not offenders, (
        "loop started directly, so it dies on the first exception; use "
        "self.start_loop(...):\n" + "\n".join(offenders)
    )


def test_the_cogs_with_loops_are_all_covered():
    """Guards the test above against silently matching nothing."""
    with_loops = set()
    for root, _dirs, files in os.walk(COGS_DIR):
        if "__pycache__" in root:
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(root, fn)
            if _loop_attribute_names(ast.parse(open(path, encoding="utf-8").read())):
                with_loops.add(os.path.basename(root))
    assert len(with_loops) >= 14, f"only found loops in {sorted(with_loops)}"


@pytest.mark.asyncio
async def test_a_loop_that_dies_in_before_loop_says_so(cog, caplog):
    """discord.py reports this one nowhere: the loop dies and every log is empty."""

    async def boom():
        raise RuntimeError("Client has not been properly initialised.")

    cog.bot.wait_until_ready = boom
    cog.start_loop(cog.ticker)

    assert await _wait_for(lambda: not cog.ticker.is_running())
    assert cog.iterations == 0
    assert any(
        r.levelname == "ERROR" and r.exc_info and "before_loop" in r.getMessage()
        for r in caplog.records
    ), "a loop that never starts must say so"


def test_cogs_are_loaded_inside_the_client_context():
    """Outside it, Client._ready does not exist yet and cog loops die in before_loop."""
    main_py = os.path.join(os.path.dirname(__file__), "..", "app", "main.py")
    with open(main_py, encoding="utf-8") as f:
        tree = ast.parse(f.read())

    main_fn = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "main"
    )

    def load_cogs_calls(node):
        return [
            c
            for c in ast.walk(node)
            if isinstance(c, ast.Call)
            and isinstance(c.func, ast.Attribute)
            and c.func.attr == "load_cogs"
        ]

    calls = load_cogs_calls(main_fn)
    assert calls, "main() no longer loads cogs"

    guarded = {
        id(c)
        for node in ast.walk(main_fn)
        if isinstance(node, ast.AsyncWith)
        for c in load_cogs_calls(node)
    }
    assert all(
        id(c) in guarded for c in calls
    ), "load_cogs() must be awaited inside `async with bot:`"
