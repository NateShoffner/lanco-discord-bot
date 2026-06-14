"""Image processor router.

Core bot functionality, not a cog. Owns the single image-bearing ``on_message``
handler for the whole bot. Cogs register an ``ImageIntent`` (see
``utils.image_router``) instead of hooking ``on_message`` themselves; the router
runs the staged flow: cheap gate, download once, one shared vision call, score,
arbitrate, dispatch.
"""

from __future__ import annotations

import logging
import mimetypes
import os
from typing import Optional

import discord
from discord.ext import commands
from utils.file_downloader import FileDownloader

from .intent import ImageCandidate, ImageContext, ImageIntent
from .vision import VisionClassifier, VisionQuestion

logger = logging.getLogger(__name__)


class ImageRouter:
    def __init__(
        self,
        bot: commands.Bot,
        cache_dir: str,
        process_all_images: bool = False,
    ):
        self.bot: commands.Bot = bot
        self.cache_dir: str = cache_dir
        # By default only the first image in a message is routed, matching every
        # existing image cog. Set True to route every attached image.
        self.process_all_images: bool = process_all_images
        self.file_downloader: FileDownloader = FileDownloader()
        self.vision: VisionClassifier = VisionClassifier()

    def _extract_candidates(self, message: discord.Message) -> list[ImageCandidate]:
        candidates: list[ImageCandidate] = []
        for att in message.attachments:
            candidates.append(
                ImageCandidate(
                    url=att.url,
                    content_type=att.content_type,
                    size=att.size,
                    source="attachment",
                )
            )
        if not candidates:
            for embed in message.embeds:
                if embed.image and embed.image.proxy_url:
                    candidates.append(
                        ImageCandidate(url=embed.image.proxy_url, source="embed")
                    )
        return candidates

    async def _download(self, candidate: ImageCandidate) -> bool:
        try:
            filename: Optional[str] = await self.file_downloader.download_file(
                candidate.url, self.cache_dir
            )
            if not filename:
                return False
            with open(filename, "rb") as f:
                candidate.data = f.read()
            candidate.filename = filename
            if not candidate.content_type:
                candidate.content_type, _ = mimetypes.guess_type(filename)
            return True
        except Exception as e:
            logger.error("Failed to download %s: %s", candidate.url, e)
            return False

    def _cleanup(self, candidate: ImageCandidate) -> None:
        if candidate.filename and os.path.exists(candidate.filename):
            try:
                os.remove(candidate.filename)
            except OSError:
                pass

    def _arbitrate(self, scored: list[tuple[ImageIntent, float]]) -> list[ImageIntent]:
        """Select winners under the isolated-by-default policy:
        drop sub-threshold scores, collapse each conflict_group to its highest
        score, always run the top-confidence intent, and run additional intents
        only if they are non-exclusive.
        """
        eligible: list[tuple[ImageIntent, float]] = [
            (i, s) for i, s in scored if s >= i.threshold
        ]
        if not eligible:
            return []

        best_in_group: dict[str, tuple[ImageIntent, float]] = {}
        ungrouped: list[tuple[ImageIntent, float]] = []
        for intent, score in eligible:
            if intent.conflict_group is None:
                ungrouped.append((intent, score))
            else:
                cur = best_in_group.get(intent.conflict_group)
                if cur is None or score > cur[1]:
                    best_in_group[intent.conflict_group] = (intent, score)

        contenders: list[tuple[ImageIntent, float]] = ungrouped + list(
            best_in_group.values()
        )
        contenders.sort(key=lambda pair: pair[1], reverse=True)

        winners: list[ImageIntent] = [contenders[0][0]]
        for intent, _ in contenders[1:]:
            if not intent.exclusive:
                winners.append(intent)
        return winners

    async def handle_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        intents: list[ImageIntent] = list(self.bot.image_processors)
        if not intents:
            return

        candidates: list[ImageCandidate] = self._extract_candidates(message)
        if not candidates:
            return
        if not self.process_all_images:
            candidates = candidates[:1]

        logger.debug(
            "message %s: %d candidate(s), %d registered intent(s)",
            message.id,
            len(candidates),
            len(intents),
        )
        for index, candidate in enumerate(candidates):
            tag: str = (
                f"msg {message.id} img[{index}]"
                if len(candidates) > 1
                else f"msg {message.id}"
            )
            await self._route_candidate(message, candidate, intents, tag)

    async def _route_candidate(
        self,
        message: discord.Message,
        candidate: ImageCandidate,
        intents: list[ImageIntent],
        tag: str,
    ) -> None:
        qualified: list[ImageIntent] = [
            i for i in intents if self._safe_predicate(i, candidate, message)
        ]
        if not qualified:
            logger.debug("%s: no intents passed the cheap gate, skipping", tag)
            return
        logger.info(
            "%s: %s (%s) qualified %s",
            tag,
            candidate.source,
            candidate.content_type or candidate.extension or "unknown",
            [i.name for i in qualified],
        )

        if not await self._download(candidate):
            logger.warning("%s: download failed, skipping", tag)
            return
        logger.debug("%s: downloaded %d bytes", tag, len(candidate.data or b""))

        try:
            questions: list[VisionQuestion] = [
                q for intent in qualified for q in intent.questions
            ]

            answers: dict = {}
            if questions:
                logger.info(
                    "%s: one shared vision call for %d intent(s), questions=%s",
                    tag,
                    len(qualified),
                    sorted({q.key for q in questions}),
                )
                media_type: str = candidate.content_type or "image/png"
                answers = await self.vision.classify(
                    candidate.data, media_type, questions
                )
                logger.info("%s: vision answers=%s", tag, answers)
            else:
                logger.debug("%s: no questions declared, skipping vision call", tag)

            ctx: ImageContext = ImageContext(
                message=message, candidate=candidate, answers=answers
            )

            scored: list[tuple[ImageIntent, float]] = [
                (intent, await self._safe_confidence(intent, ctx))
                for intent in qualified
            ]
            logger.info(
                "%s: scores=%s",
                tag,
                {i.name: round(s, 2) for i, s in scored},
            )

            winners: list[ImageIntent] = self._arbitrate(scored)
            if not winners:
                logger.info(
                    "%s: no intent cleared its threshold, nothing dispatched", tag
                )
                return
            logger.info("%s: dispatching %s", tag, [i.name for i in winners])

            for intent in winners:
                await self._safe_process(intent, ctx)
        finally:
            self._cleanup(candidate)

    def _safe_predicate(
        self,
        intent: ImageIntent,
        candidate: ImageCandidate,
        message: discord.Message,
    ) -> bool:
        try:
            return bool(intent.cheap_predicate(candidate, message))
        except Exception as e:
            logger.error("Predicate error in %s: %s", intent.name, e)
            return False

    async def _safe_confidence(self, intent: ImageIntent, ctx: ImageContext) -> float:
        try:
            return float(await intent.confidence(ctx))
        except Exception as e:
            logger.error("Confidence error in %s: %s", intent.name, e)
            return 0.0

    async def _safe_process(self, intent: ImageIntent, ctx: ImageContext) -> None:
        try:
            await intent.process(ctx)
        except Exception as e:
            logger.error("Process error in %s: %s", intent.name, e)
