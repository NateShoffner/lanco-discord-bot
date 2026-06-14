"""Core types for the image processor router.

A cog declares an ``ImageIntent`` describing what it wants to act on and the work
it does. The router (``utils.image_router.router``) evaluates every registered
intent against an incoming image, arbitrates by confidence, and dispatches the
winner(s).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional

import discord

if TYPE_CHECKING:
    from cogs.lancocog import LancoCog

    from .vision import VisionQuestion


@dataclass
class ImageCandidate:
    """A single image extracted from a message, downloaded at most once.

    ``filename`` and ``data`` are populated only after the router's download
    stage; the cheap predicate runs before download and must rely solely on the
    metadata fields.
    """

    url: str
    content_type: Optional[str] = None
    size: Optional[int] = None
    source: str = "attachment"  # "attachment" | "embed"
    filename: Optional[str] = None
    data: Optional[bytes] = None

    @property
    def extension(self) -> str:
        tail: list[str] = self.url.split("?")[0].rsplit(".", 1)
        return tail[-1].lower() if len(tail) == 2 else ""


@dataclass
class ImageContext:
    """Everything an intent needs to score and process a candidate.

    ``answers`` holds the result of the single shared vision pass: the union of
    every qualifying intent's questions, asked once.
    """

    message: discord.Message
    candidate: ImageCandidate
    answers: dict[str, Any] = field(default_factory=dict)

    def answer(self, key: str, default: Any = None) -> Any:
        return self.answers.get(key, default)


CheapPredicate = Callable[[ImageCandidate, discord.Message], bool]
ConfidenceFn = Callable[[ImageContext], Awaitable[float]]
ProcessFn = Callable[[ImageContext], Awaitable[None]]


@dataclass
class ImageIntent:
    """A cog's declared interest in images, registered with the router.

    Exclusivity is isolated by default: an intent runs only as the
    top-confidence winner unless ``exclusive=False`` lets it coexist. Intents
    sharing a non-None ``conflict_group`` always compete, highest confidence
    winning regardless of ``exclusive``.
    """

    cog: LancoCog
    name: str
    cheap_predicate: CheapPredicate
    confidence: ConfidenceFn
    process: ProcessFn
    questions: list[VisionQuestion] = field(default_factory=list)
    conflict_group: Optional[str] = None
    exclusive: bool = True
    threshold: float = 0.5
