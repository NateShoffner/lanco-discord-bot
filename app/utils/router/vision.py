"""Shared vision pass for the image router.

Each intent declares the ``VisionQuestion`` objects it cares about. The router
unions all questions from the qualifying intents and asks them in a single model
call per image, then hands the structured answers to every intent. The
classifier builds a Pydantic model on the fly from the questions so the model is
forced to return exactly the keyed fields the intents expect.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from pydantic import BaseModel, Field, create_model
from pydantic_ai import Agent, BinaryContent

logger = logging.getLogger(__name__)

_KIND_TYPES: dict[str, tuple[Any, Any]] = {
    "bool": (bool, False),
    "int": (Optional[int], None),
    "str": (Optional[str], None),
    "float": (Optional[float], None),
}


@dataclass(frozen=True)
class VisionQuestion:
    """A single thing an intent wants to know about an image.

    ``key`` is the field name the intent reads out of ``ImageContext.answers``;
    ``classify`` de-duplicates by ``key`` so multiple intents asking the same
    thing collapse into one field.
    """

    key: str
    prompt: str
    kind: str = "bool"


class VisionClassifier:
    def __init__(self, model: str = "openai:gpt-5-nano"):
        self.model: str = model

    def _build_output_model(self, questions: list[VisionQuestion]) -> type[BaseModel]:
        fields: dict[str, tuple[Any, Any]] = {}
        for q in questions:
            if q.kind not in _KIND_TYPES:
                logger.warning(
                    "unknown question kind %r for %r, treating as bool", q.kind, q.key
                )
            py_type, default = _KIND_TYPES.get(q.kind, _KIND_TYPES["bool"])
            fields[q.key] = (py_type, Field(default, description=q.prompt))
        return create_model("VisionAnswers", **fields)

    async def classify(
        self,
        image_bytes: bytes,
        media_type: str,
        questions: list[VisionQuestion],
    ) -> dict[str, Any]:
        """Ask all ``questions`` of one image in a single model call. Returns a
        dict keyed by each question's ``key``, or ``{}`` if there are no
        questions or the model call fails (intents then score from the absence
        of answers rather than crashing dispatch).
        """
        if not questions:
            return {}

        seen: set[str] = set()
        unique: list[VisionQuestion] = []
        for q in questions:
            if q.key not in seen:
                seen.add(q.key)
                unique.append(q)

        if len(unique) < len(questions):
            logger.debug(
                "deduped %d question(s) down to %d", len(questions), len(unique)
            )

        output_model: type[BaseModel] = self._build_output_model(unique)
        prompt_lines: list[str] = ["Answer the following about the image:"]
        for q in unique:
            prompt_lines.append(f"- {q.key}: {q.prompt}")

        logger.debug(
            "classifying %d bytes (%s) for keys %s",
            len(image_bytes),
            media_type,
            [q.key for q in unique],
        )

        agent: Agent = Agent(
            model=self.model,
            system_prompt="You are an image classifier. Answer precisely.",
            output_type=output_model,
        )

        try:
            result = await agent.run(
                [
                    "\n".join(prompt_lines),
                    BinaryContent(data=image_bytes, media_type=media_type),
                ]
            )
        except Exception as e:
            logger.error("Vision classification failed: %s", e)
            return {}

        return result.output.model_dump()
