import asyncio
import os
import sys


def _run():
    # main.py uses bare imports (from cogs..., from db...) that require app/ on sys.path,
    # matching the behavior of `python app/main.py` which adds the script directory automatically.
    app_dir = os.path.dirname(os.path.abspath(__file__))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    from app.main import main

    asyncio.run(main())


# BOT_ENV selects the .env.<env> file and, through it, dev mode and the APM
# environment. Set in the real process environment so it outranks that file:
# otherwise a DEV_MODE=false left in a dotenv would demote `poetry run dev`.


def dev():
    os.environ["BOT_ENV"] = "dev"
    _run()


def prod():
    os.environ["BOT_ENV"] = "prod"
    _run()


def test():
    import pytest

    os.environ["BOT_ENV"] = "test"
    raise SystemExit(pytest.main([]))
