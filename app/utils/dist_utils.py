import os
import subprocess

import toml

bot_version = None
commit_hash = None


def get_bot_version():
    global bot_version
    if not bot_version:
        with open("pyproject.toml", "r") as f:
            pyproject = toml.load(f)
            bot_version = pyproject["tool"]["poetry"]["version"]
    return bot_version


def get_commit_hash():
    # Cached like the version above: the hash cannot change while the process
    # runs, and without this every caller spawns a git subprocess.
    global commit_hash
    if commit_hash:
        return commit_hash
    # Check env var first (can be injected at build time via Docker ARG/ENV)
    commit_hash = os.getenv("GIT_COMMIT_HASH")
    if commit_hash:
        return commit_hash
    try:
        commit_hash = (
            subprocess.check_output(["git", "rev-parse", "HEAD"])
            .decode("utf-8")
            .strip()
        )
    except Exception:
        commit_hash = "unknown"
    return commit_hash


def get_service_version():
    """Version plus short commit, identifying the exact build to Elastic.

    Shared by the APM service version and the ECS log fields so an error and
    the log lines around it agree about which build produced them.
    """
    return f"{get_bot_version()}+{(get_commit_hash() or 'unknown')[:7]}"


def strtobool(val):
    """Convert a string representation of truth to true (1) or false (0).
    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
    are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
    'val' is anything else.
    """
    val = val.lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return 1
    elif val in ("n", "no", "f", "false", "off", "0"):
        return 0
    else:
        raise ValueError("invalid truth value %r" % (val,))
