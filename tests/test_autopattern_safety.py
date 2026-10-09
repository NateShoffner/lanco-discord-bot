"""An admin-supplied regex must not be able to stall the bot.

`autoreact` and `autoresponse` run a stored pattern against every message in
every guild, on the event loop, with `re` and no bound. One pattern that
backtracks catastrophically (`(a|a)*$` is enough) freezes the whole process for
every guild until the cog is reloaded, and one guild's admin can do that to
everyone else's.

So matching goes through `utils.common.matches_pattern`, which has a real match
deadline, and saving goes through `is_safe_regex`, which runs the pattern once
before storing it. The static check at the bottom is the one that matters
long-term: it fails if either cog goes back to calling `re` directly.
"""

import ast
import os
import time

import pytest
from utils.common import MATCH_TIMEOUT, is_regex, is_safe_regex, matches_pattern

COGS_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "cogs")

#: Classic catastrophic-backtracking patterns, with input that triggers it.
EVIL = ("(a|a)*$", "a" * 40 + "!")


def test_a_plain_pattern_still_matches():
    assert matches_pattern(r"\bhello\b", "well hello there")
    assert not matches_pattern(r"\bhello\b", "goodbye")


def test_a_substring_match_is_enough():
    """The old code used re.findall, which matches anywhere in the string."""
    assert matches_pattern("dog", "hotdog time")


def test_a_catastrophic_pattern_gives_up_quickly():
    pattern, text = EVIL
    started = time.monotonic()
    assert matches_pattern(pattern, text) is False
    # the deadline, plus generous slack for a loaded CI box
    assert time.monotonic() - started < MATCH_TIMEOUT + 2


def test_a_malformed_pattern_does_not_raise():
    """The pattern is validated on save, but rows predate that validation."""
    assert matches_pattern("(unclosed", "anything") is False


def test_oversized_input_is_truncated_not_rejected():
    assert matches_pattern("^x+", "x" * 100_000)


def test_is_safe_regex_accepts_an_ordinary_pattern():
    assert is_safe_regex(r"\bcat(s)?\b")
    assert is_safe_regex("hotdog")


def test_is_safe_regex_rejects_a_catastrophic_pattern():
    pattern = EVIL[0]
    # it parses fine, which is exactly why compiling alone was not enough
    assert is_regex(pattern)
    assert not is_safe_regex(pattern)


def test_is_safe_regex_rejects_a_malformed_pattern():
    assert not is_safe_regex("(unclosed")


@pytest.mark.parametrize("cog", ["autoreact", "autoresponse"])
def test_pattern_cogs_do_not_match_with_the_stdlib_re(cog):
    """`re` has no way to abandon a match in progress, so any use of it on a
    stored pattern is the freeze coming back.
    """
    path = os.path.join(COGS_DIR, cog, f"{cog}.py")
    tree = ast.parse(open(path, encoding="utf-8").read())
    offenders = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "re"
        ):
            offenders.append(f"{cog}.py:{node.lineno} re.{node.func.attr}")
    assert not offenders, "unbounded regex on the event loop:\n" + "\n".join(offenders)


@pytest.mark.parametrize("cog", ["autoreact", "autoresponse"])
def test_pattern_cogs_validate_on_save(cog):
    path = os.path.join(COGS_DIR, cog, f"{cog}.py")
    source = open(path, encoding="utf-8").read()
    assert "is_safe_regex(" in source, f"{cog} stores a pattern without vetting it"
