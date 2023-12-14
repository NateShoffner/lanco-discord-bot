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
    global commit_hash
    if not commit_hash:
        try:
            commit_hash = (
                subprocess.check_output(["git", "rev-parse", "HEAD"])
                .decode("utf-8")
                .strip()
            )
        except:
            commit_hash = "Unknown"
    return commit_hash
