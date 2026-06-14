"""Base class for image-processing cogs.

A cog that reacts to images subclasses ``ImageProcessorCog`` and calls
``register_image_intent`` (typically in ``cog_load``). It never hooks
``on_message`` or downloads anything; the router calls back into the registered
``confidence`` / ``process`` functions.
"""

from __future__ import annotations

import discord
from cogs.lancocog import LancoCog

from .intent import CheapPredicate, ConfidenceFn, ImageCandidate, ImageIntent, ProcessFn
from .vision import VisionQuestion

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


class ImageProcessorCog(LancoCog):
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
    ) -> ImageIntent:
        intent: ImageIntent = ImageIntent(
            cog=self,
            name=name,
            cheap_predicate=cheap_predicate,
            confidence=confidence,
            process=process,
            questions=questions or [],
            conflict_group=conflict_group,
            exclusive=exclusive,
            threshold=threshold,
        )
        self.bot.register_image_processor(intent)
        return intent

    @staticmethod
    def is_image(candidate: ImageCandidate, message: discord.Message) -> bool:
        """Default cheap predicate: the candidate looks like a raster image,
        judged on metadata only (no download, no AI).
        """
        if candidate.content_type and candidate.content_type.startswith("image/"):
            return True
        return candidate.extension in IMAGE_EXTENSIONS
