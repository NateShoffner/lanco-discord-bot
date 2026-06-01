import asyncio
import os
import sys


def _run(env=None):
    if env:
        sys.argv = ["main.py", env]
    # main.py uses bare imports (from cogs..., from db...) that require app/ on sys.path,
    # matching the behavior of `python app/main.py` which adds the script directory automatically.
    app_dir = os.path.dirname(os.path.abspath(__file__))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    from app.main import main

    asyncio.run(main())


def dev():
    _run("dev")


def prod():
    _run()


def test():
    import pytest

    raise SystemExit(pytest.main([]))
