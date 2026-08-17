"""Which deployment environment this process is running as.

``BOT_ENV`` is the single source of truth: dev mode, the dotenv file that gets
loaded, and the Elastic APM environment all derive from it, so they cannot
disagree.

Resolution is two-phase. What the *process* declares (``BOT_ENV``, argv, or a
legacy ``DEV_MODE``) is settled before any file is read and outranks the file.
Without that, ``load_dotenv(override=True)`` reading a ``DEV_MODE=false`` out
of ``.env`` would quietly demote ``poetry run dev`` to production.
"""

import logging
import os
import sys
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

DEV = "dev"
PROD = "prod"
TEST = "test"

# Anything unlisted passes through lowercased, so a deployment can invent a
# name like "staging" and have it reach APM intact; only "dev" is dev mode.
_ALIASES = {"development": DEV, "production": PROD}


def normalize(value: Optional[str]) -> Optional[str]:
    """Canonical form of an environment name, or None if there isn't one."""
    if not value or not value.strip():
        return None
    key = value.strip().lower()
    return _ALIASES.get(key, key)


def _declared_by_process(argv: list[str]) -> Optional[str]:
    """The environment the process declares, before any file is read."""
    explicit = normalize(os.getenv("BOT_ENV"))
    if explicit:
        return explicit
    if len(argv) > 1:
        from_argv = normalize(argv[1])
        if from_argv:
            return from_argv
    if os.getenv("DEV_MODE", "").lower() == "true":
        return DEV
    return None


def env_file_candidates(env: Optional[str]) -> list[str]:
    """Dotenv paths to try, most specific first.

    ``.env`` remains a fallback so a single-file setup keeps working.
    """
    if env == TEST:
        # The one environment that must not fall back: the suite imports main,
        # so a developer's .env would replace the in-memory test database with
        # the real one and pull in live credentials.
        return [f".env.{TEST}"]
    candidates = []
    if env:
        candidates.append(f".env.{env}")
    candidates.append(".env")
    return candidates


def load_environment(argv: Optional[list[str]] = None) -> str:
    """Resolve the environment, load its dotenv file, and normalize BOT_ENV and
    DEV_MODE to agree. Returns the environment name. Safe to call repeatedly.
    """
    argv = sys.argv if argv is None else argv
    declared = _declared_by_process(argv)

    for path in env_file_candidates(declared):
        if os.path.exists(path):
            load_dotenv(path, override=True)
            logger.info(f"Loaded environment file: {path}")
            break
    else:
        logger.info("No .env file found, using environment variables")

    env = declared or normalize(os.getenv("BOT_ENV"))
    if env is None:
        env = DEV if os.getenv("DEV_MODE", "").lower() == "true" else PROD

    # Written back so later readers, including anything still checking
    # DEV_MODE directly, see one consistent answer.
    os.environ["BOT_ENV"] = env
    os.environ["DEV_MODE"] = "true" if env == DEV else "false"
    logger.info(f"Environment: {env}")
    return env


def current() -> str:
    """The resolved environment. Defaults to prod so an unconfigured process
    never accidentally behaves like a development one.
    """
    return normalize(os.getenv("BOT_ENV")) or PROD


def is_dev() -> bool:
    return current() == DEV
