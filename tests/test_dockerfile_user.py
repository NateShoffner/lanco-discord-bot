"""The container must not run the bot as root.

The image mounts the host's ./data and ./logs, holds every API key in its
environment, and runs code that fetches and parses whatever gets posted in
chat. As root, any bug that gets as far as writing a file writes it as root on
the host volume, and the process can rewrite its own source in /app.

A static check rather than a build, because building the image in CI for this
would cost minutes to assert one line.
"""

import os

DOCKERFILE = os.path.join(os.path.dirname(__file__), "..", "Dockerfile")


def _logical_lines() -> list[tuple[int, str]]:
    """The Dockerfile with backslash continuations joined, so a RUN body split
    over several lines reads as one instruction.
    """
    lines = []
    start = None
    buffer = ""
    with open(DOCKERFILE, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if start is None:
                start = lineno
            if stripped.endswith("\\"):
                buffer += stripped[:-1].strip() + " "
                continue
            lines.append((start, buffer + stripped))
            start = None
            buffer = ""
    return lines


def _directives(name: str) -> list[tuple[int, str]]:
    return [
        (lineno, body.split(None, 1)[1].strip())
        for lineno, body in _logical_lines()
        if body.upper().startswith(f"{name} ")
    ]


def test_the_runtime_stage_declares_a_non_root_user():
    users = _directives("USER")
    assert users, "no USER directive, so the bot runs as root"
    _, final = users[-1]
    assert final.split(":")[0] not in ("root", "0"), f"USER is {final}"


def test_the_user_switch_is_the_last_thing_before_the_command():
    """A USER before the COPY/RUN lines would leave them unprivileged and the
    process root again, which is backwards.
    """
    user_line = _directives("USER")[-1][0]
    later = [
        lineno
        for name in ("COPY", "RUN", "ADD")
        for lineno, _ in _directives(name)
        if lineno > user_line
    ]
    assert not later, f"privileged build steps on lines {later} run after USER"


def test_the_writable_directories_are_owned_by_that_user():
    """Both are bind mounts in compose, so this only covers a run without them,
    but getting it wrong here hides the problem until the volumes are dropped.
    """
    chowns = [body for _, body in _directives("RUN") if "chown" in body]
    assert chowns, "no chown of the writable paths"
    joined = " ".join(chowns)
    assert "/app/data" in joined
    assert "/app/logs" in joined
