"""Tests for environment resolution.

The behaviour that matters is precedence. Before BOT_ENV existed, `poetry run
dev` set DEV_MODE in the process and main then loaded a dotenv file with
override=True, so a DEV_MODE=false sitting in .env silently demoted a dev run
to production and there was no way to tell dev and prod apart in APM. These
tests pin the rule that what the process declares outranks what a file says.
"""

import os

import pytest
from utils import env


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    """Run each case in an empty directory with no environment carried in."""
    for name in ("BOT_ENV", "DEV_MODE", "SOME_VALUE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def write_env_file(directory, name: str, body: str) -> None:
    (directory / name).write_text(body, encoding="utf-8")


def test_defaults_to_prod_with_nothing_configured(clean_env):
    assert env.load_environment(argv=["main.py"]) == env.PROD
    assert env.is_dev() is False
    assert os.environ["DEV_MODE"] == "false"


def test_bot_env_selects_matching_dotenv_file(clean_env, monkeypatch):
    write_env_file(clean_env, ".env.dev", "SOME_VALUE=from-dev\n")
    write_env_file(clean_env, ".env", "SOME_VALUE=from-plain\n")
    monkeypatch.setenv("BOT_ENV", "dev")

    assert env.load_environment(argv=["main.py"]) == env.DEV
    assert os.environ["SOME_VALUE"] == "from-dev"


def test_falls_back_to_plain_env_when_no_specific_file(clean_env, monkeypatch):
    write_env_file(clean_env, ".env", "SOME_VALUE=from-plain\n")
    monkeypatch.setenv("BOT_ENV", "prod")

    assert env.load_environment(argv=["main.py"]) == env.PROD
    assert os.environ["SOME_VALUE"] == "from-plain"


def test_process_env_outranks_dev_mode_in_the_file(clean_env, monkeypatch):
    """The regression this exists for: .env must not demote a dev run."""
    write_env_file(clean_env, ".env", "DEV_MODE=false\n")
    monkeypatch.setenv("BOT_ENV", "dev")

    assert env.load_environment(argv=["main.py"]) == env.DEV
    assert env.is_dev() is True
    assert os.environ["DEV_MODE"] == "true"


def test_argv_is_honoured_when_bot_env_is_unset(clean_env):
    write_env_file(clean_env, ".env.dev", "SOME_VALUE=from-dev\n")

    assert env.load_environment(argv=["main.py", "dev"]) == env.DEV
    assert os.environ["SOME_VALUE"] == "from-dev"


def test_legacy_dev_mode_still_selects_dev(clean_env, monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")

    assert env.load_environment(argv=["main.py"]) == env.DEV
    assert os.environ["BOT_ENV"] == env.DEV


def test_dev_mode_from_the_file_is_honoured_when_nothing_else_declares(clean_env):
    write_env_file(clean_env, ".env", "DEV_MODE=true\n")

    assert env.load_environment(argv=["main.py"]) == env.DEV
    assert os.environ["BOT_ENV"] == env.DEV


def test_test_env_never_falls_back_to_plain_env(clean_env, monkeypatch):
    """A test run must not inherit a developer's live configuration."""
    write_env_file(clean_env, ".env", "SOME_VALUE=from-plain\n")
    monkeypatch.setenv("BOT_ENV", "test")

    assert env.load_environment(argv=["main.py"]) == env.TEST
    assert "SOME_VALUE" not in os.environ
    assert env.env_file_candidates(env.TEST) == [".env.test"]


def test_aliases_are_normalized():
    assert env.normalize("Production") == env.PROD
    assert env.normalize("  DEVELOPMENT ") == env.DEV
    assert env.normalize("") is None
    assert env.normalize(None) is None


def test_unknown_names_pass_through(clean_env, monkeypatch):
    """A deployment can invent an environment; only 'dev' means dev mode."""
    monkeypatch.setenv("BOT_ENV", "staging")

    assert env.load_environment(argv=["main.py"]) == "staging"
    assert env.is_dev() is False
