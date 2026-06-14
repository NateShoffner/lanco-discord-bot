"""Base class for cogs that register routing intents.

Subclass ``ProcessorCog`` (a ``LancoCog``) and register intents in ``cog_load``.
The cog never hooks ``on_message`` or downloads anything; the router calls back
into the registered ``confidence`` / ``process`` functions.
"""

from __future__ import annotations

import discord
from cogs.lancocog import LancoCog

from .base import (
    LEVEL_FILE,
    LEVEL_MESSAGE,
    Candidate,
    CheapPredicate,
    ConfidenceFn,
    Intent,
    IntentScope,
    ProcessFn,
)
from .image import IMAGE_EXTENSIONS, ImageIntent, looks_like_image
from .vision import VisionQuestion


class ProcessorCog(LancoCog):
    def register_message_intent(
        self,
        name: str,
        cheap_predicate: CheapPredicate,
        confidence: ConfidenceFn,
        process: ProcessFn,
        conflict_group: str | None = None,
        exclusive: bool = True,
        threshold: float = 0.5,
        scope: IntentScope | None = None,
    ) -> Intent:
        return self._register(
            Intent(
                cog=self,
                name=name,
                cheap_predicate=cheap_predicate,
                confidence=confidence,
                process=process,
                conflict_group=conflict_group,
                exclusive=exclusive,
                threshold=threshold,
                level=LEVEL_MESSAGE,
                scope=scope,
            )
        )

    def register_file_intent(
        self,
        name: str,
        cheap_predicate: CheapPredicate,
        confidence: ConfidenceFn,
        process: ProcessFn,
        conflict_group: str | None = None,
        exclusive: bool = True,
        threshold: float = 0.5,
        scope: IntentScope | None = None,
    ) -> Intent:
        return self._register(
            Intent(
                cog=self,
                name=name,
                cheap_predicate=cheap_predicate,
                confidence=confidence,
                process=process,
                conflict_group=conflict_group,
                exclusive=exclusive,
                threshold=threshold,
                level=LEVEL_FILE,
                scope=scope,
            )
        )

    def register_image_intent(
        self,
        name: str,
        cheap_predicate: CheapPredicate,
        confidence: ConfidenceFn,
        process: ProcessFn,
        questions: list[VisionQuestion] | None = None,
        conflict_group: str | None = None,
        exclusive: bool = True,
        threshold: float = 0.5,
        scope: IntentScope | None = None,
    ) -> ImageIntent:
        return self._register(
            ImageIntent(
                cog=self,
                name=name,
                cheap_predicate=cheap_predicate,
                confidence=confidence,
                process=process,
                questions=questions or [],
                conflict_group=conflict_group,
                exclusive=exclusive,
                threshold=threshold,
                scope=scope,
            )
        )

    def _register(self, intent: Intent) -> Intent:
        self.bot.register_processor(intent)
        return intent

    @staticmethod
    def is_image(candidate: Candidate, message: discord.Message) -> bool:
        """Default cheap predicate for image intents: the candidate looks like a
        raster image, judged on metadata only (no download, no AI).
        """
        url = getattr(candidate, "url", "") or ""
        content_type = getattr(candidate, "content_type", None)
        return looks_like_image(content_type, url)
