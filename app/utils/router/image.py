"""Image router: filters file candidates to images and runs one shared vision
call answering the union of every qualifying image intent's questions.

This is the deepest router in the stack and the one the bot instantiates; it
inherits message- and file-level handling.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import discord

from .base import (
    LEVEL_FILE,
    LEVEL_IMAGE,
    LEVEL_MESSAGE,
    Candidate,
    Intent,
    RouterContext,
)
from .file import FileCandidate, FileRouter
from .vision import VisionClassifier, VisionQuestion

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS: set[str] = {
    "png",
    "jpg",
    "jpeg",
    "webp",
    "gif",
    "bmp",
    "heic",
    "avif",
}


@dataclass
class ImageCandidate(FileCandidate):
    answers: dict[str, Any] = field(default_factory=dict)  # set by the vision pass

    def __post_init__(self) -> None:
        self.level = LEVEL_IMAGE


@dataclass
class ImageContext(RouterContext):
    candidate: ImageCandidate = None
    answers: dict[str, Any] = field(default_factory=dict)

    def answer(self, key: str, default: Any = None) -> Any:
        return self.answers.get(key, default)


@dataclass
class ImageIntent(Intent):
    questions: list[VisionQuestion] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.level = LEVEL_IMAGE


def looks_like_image(content_type: str | None, url: str) -> bool:
    if content_type and content_type.startswith("image/"):
        return True
    tail = url.split("?")[0].rsplit(".", 1)
    return len(tail) == 2 and tail[-1].lower() in IMAGE_EXTENSIONS


class ImageRouter(FileRouter):
    LEVELS = (LEVEL_MESSAGE, LEVEL_FILE, LEVEL_IMAGE)

    def __init__(self, bot, cache_dir: str, process_all_images: bool = False):
        super().__init__(bot, cache_dir)
        # When False, only the first extracted candidate is routed, matching the
        # other image cogs. When True, every attachment is routed.
        self.process_all_images: bool = process_all_images
        self.vision: VisionClassifier = VisionClassifier()

    def _make_file_candidate(self, **kwargs) -> FileCandidate:
        if looks_like_image(kwargs.get("content_type"), kwargs.get("url", "")):
            return ImageCandidate(**kwargs)
        return FileCandidate(**kwargs)

    def _extract_candidates(self, message: discord.Message) -> list[Candidate]:
        candidates = super()._extract_candidates(message)
        if not self.process_all_images:
            # keep all message-level candidates plus the first file/image one
            files = [c for c in candidates if isinstance(c, FileCandidate)]
            non_files = [c for c in candidates if not isinstance(c, FileCandidate)]
            candidates = non_files + files[:1]
        return candidates

    async def _enrich(
        self, qualified: list[Intent], candidate: Candidate, message: discord.Message
    ) -> None:
        if not isinstance(candidate, ImageCandidate):
            return
        questions: list[VisionQuestion] = [
            q for i in qualified if isinstance(i, ImageIntent) for q in i.questions
        ]
        if not questions:
            return
        logger.info(
            "one shared vision call for %d intent(s), questions=%s",
            sum(isinstance(i, ImageIntent) for i in qualified),
            sorted({q.key for q in questions}),
        )
        media_type = candidate.content_type or "image/png"
        candidate.answers = await self.vision.classify(
            candidate.data, media_type, questions
        )
        logger.info("vision answers=%s", candidate.answers)

    def _build_context(
        self, message: discord.Message, candidate: Candidate
    ) -> RouterContext:
        if isinstance(candidate, ImageCandidate):
            return ImageContext(
                message=message, candidate=candidate, answers=candidate.answers
            )
        return super()._build_context(message, candidate)
