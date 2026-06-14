"""Generic message router.

The base of a three-layer routing stack:

    MessageRouter            this module: registry, gate, score, arbitrate, dispatch
      -> FileRouter          utils.router.file: extract attachments, download once
           -> ImageRouter    utils.router.image: filter to images, one shared vision call

A cog registers an ``Intent`` (or a ``FileIntent`` / ``ImageIntent``) on the
bot's single ``processors`` list. The deepest instantiated router owns the one
``on_message`` handler and runs the full pipeline; each intent is evaluated
against the candidate level it targets.

The universal unit is a ``Candidate``. A message-level candidate just wraps the
message (no file, no bytes); subclasses extend it with a URL, downloaded bytes,
and vision answers. This lets one pipeline serve every level.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional

import discord

if TYPE_CHECKING:
    from cogs.lancocog import LancoCog

logger = logging.getLogger(__name__)

# Each intent targets one candidate level; the router only evaluates an intent
# against candidates at or below its level. The order is broad -> specific: an
# image candidate is also a file candidate, so it serves both file and image
# intents (and is downloaded once).
LEVEL_MESSAGE = "message"
LEVEL_FILE = "file"
LEVEL_IMAGE = "image"

LEVEL_ORDER: tuple[str, ...] = (LEVEL_MESSAGE, LEVEL_FILE, LEVEL_IMAGE)


def candidate_accepts(candidate_level: str, intent_level: str) -> bool:
    """True if a candidate at ``candidate_level`` can be evaluated by an intent
    targeting ``intent_level`` (same level, or candidate is more specific).
    """
    return LEVEL_ORDER.index(candidate_level) >= LEVEL_ORDER.index(intent_level)


@dataclass
class Candidate:
    """A unit of work extracted from a message. The message level carries only
    the message itself; subclasses add a URL, bytes, etc.
    """

    level: str = LEVEL_MESSAGE


@dataclass
class RouterContext:
    """Passed to an intent's ``confidence`` and ``process``."""

    message: discord.Message
    candidate: Candidate


CheapPredicate = Callable[[Candidate, discord.Message], bool]
ConfidenceFn = Callable[["RouterContext"], Awaitable[float]]
ProcessFn = Callable[["RouterContext"], Awaitable[None]]


@dataclass
class Intent:
    """A cog's declared interest, registered with the router.

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
    conflict_group: Optional[str] = None
    exclusive: bool = True
    threshold: float = 0.5
    level: str = LEVEL_MESSAGE


class MessageRouter:
    """Generic pipeline: extract candidates, gate, enrich, score, arbitrate,
    dispatch. Subclasses override ``_extract_candidates`` (per level) and the
    ``_prepare`` / ``_enrich`` hooks.
    """

    #: candidate levels this router knows how to extract and run
    LEVELS: tuple[str, ...] = (LEVEL_MESSAGE,)

    def __init__(self, bot):
        self.bot = bot

    # --- extension points -------------------------------------------------

    def _extract_candidates(self, message: discord.Message) -> list[Candidate]:
        """One candidate per message at this level."""
        return [Candidate(level=LEVEL_MESSAGE)]

    async def _prepare(self, candidate: Candidate) -> bool:
        """Fetch whatever the candidate needs before scoring (e.g. download).
        Return False to skip the candidate. No-op at the message level.
        """
        return True

    async def _enrich(
        self, qualified: list[Intent], candidate: Candidate, message: discord.Message
    ) -> None:
        """Run a shared, expensive step once for all qualifying intents (e.g. a
        vision call), storing the result on the candidate. No-op by default.
        """

    def _build_context(
        self, message: discord.Message, candidate: Candidate
    ) -> RouterContext:
        return RouterContext(message=message, candidate=candidate)

    def _cleanup(self, candidate: Candidate) -> None:
        """Release any resources acquired in ``_prepare``. No-op by default."""

    # --- pipeline ---------------------------------------------------------

    async def handle_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        intents: list[Intent] = [
            i for i in self.bot.processors if i.level in self.LEVELS
        ]
        if not intents:
            return

        candidates: list[Candidate] = self._extract_candidates(message)
        if not candidates:
            return

        logger.debug(
            "message %s: %d candidate(s), %d intent(s)",
            message.id,
            len(candidates),
            len(intents),
        )
        for index, candidate in enumerate(candidates):
            tag: str = (
                f"msg {message.id} [{index}]"
                if len(candidates) > 1
                else f"msg {message.id}"
            )
            applicable = [
                i for i in intents if candidate_accepts(candidate.level, i.level)
            ]
            if applicable:
                await self._route_candidate(message, candidate, applicable, tag)

    async def _route_candidate(
        self,
        message: discord.Message,
        candidate: Candidate,
        intents: list[Intent],
        tag: str,
    ) -> None:
        qualified: list[Intent] = [
            i for i in intents if self._safe_predicate(i, candidate, message)
        ]
        if not qualified:
            logger.debug("%s: nothing passed the %s gate", tag, candidate.level)
            return
        logger.info(
            "%s: %s qualified %s", tag, candidate.level, [i.name for i in qualified]
        )

        if not await self._prepare(candidate):
            logger.warning("%s: prepare failed, skipping", tag)
            return

        try:
            await self._enrich(qualified, candidate, message)
            ctx: RouterContext = self._build_context(message, candidate)

            scored: list[tuple[Intent, float]] = [
                (intent, await self._safe_confidence(intent, ctx))
                for intent in qualified
            ]
            logger.info("%s: scores=%s", tag, {i.name: round(s, 2) for i, s in scored})

            winners: list[Intent] = self._arbitrate(scored)
            if not winners:
                logger.info("%s: nothing cleared threshold", tag)
                return
            logger.info("%s: dispatching %s", tag, [i.name for i in winners])

            for intent in winners:
                await self._safe_process(intent, ctx)
        finally:
            self._cleanup(candidate)

    def _arbitrate(self, scored: list[tuple[Intent, float]]) -> list[Intent]:
        """Select winners under the isolated-by-default policy: drop sub-threshold
        scores, collapse each conflict_group to its highest score, always run the
        top-confidence intent, and run additional intents only if non-exclusive.
        """
        eligible = [(i, s) for i, s in scored if s >= i.threshold]
        if not eligible:
            return []

        best_in_group: dict[str, tuple[Intent, float]] = {}
        ungrouped: list[tuple[Intent, float]] = []
        for intent, score in eligible:
            if intent.conflict_group is None:
                ungrouped.append((intent, score))
            else:
                cur = best_in_group.get(intent.conflict_group)
                if cur is None or score > cur[1]:
                    best_in_group[intent.conflict_group] = (intent, score)

        contenders = ungrouped + list(best_in_group.values())
        contenders.sort(key=lambda pair: pair[1], reverse=True)

        winners: list[Intent] = [contenders[0][0]]
        for intent, _ in contenders[1:]:
            if not intent.exclusive:
                winners.append(intent)
        return winners

    # --- safety wrappers: one bad intent must not break the others --------

    def _safe_predicate(
        self, intent: Intent, candidate: Candidate, message: discord.Message
    ) -> bool:
        try:
            return bool(intent.cheap_predicate(candidate, message))
        except Exception as e:
            logger.error("Predicate error in %s: %s", intent.name, e)
            return False

    async def _safe_confidence(self, intent: Intent, ctx: RouterContext) -> float:
        try:
            return float(await intent.confidence(ctx))
        except Exception as e:
            logger.error("Confidence error in %s: %s", intent.name, e)
            return 0.0

    async def _safe_process(self, intent: Intent, ctx: RouterContext) -> None:
        try:
            await intent.process(ctx)
        except Exception as e:
            logger.error("Process error in %s: %s", intent.name, e)
