import subprocess

import toml

bot_version = None


def get_bot_version():
    global bot_version
    if not bot_version:
        with open("pyproject.toml", "r") as f:
            pyproject = toml.load(f)
            bot_version = pyproject["tool"]["poetry"]["version"]
    return bot_version


def get_commit_hash():
    try:
        commit_hash = (
            subprocess.check_output(["git", "rev-parse", "HEAD"])
            .decode("utf-8")
            .strip()
        )
    except:
        commit_hash = "Unknown"
    return commit_hash


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
