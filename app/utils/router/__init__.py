from .base import (
    LEVEL_FILE,
    LEVEL_IMAGE,
    LEVEL_MESSAGE,
    Candidate,
    Intent,
    MessageRouter,
    RouterContext,
)
from .cog import ProcessorCog
from .file import FileCandidate, FileContext, FileIntent, FileRouter
from .image import (
    IMAGE_EXTENSIONS,
    ImageCandidate,
    ImageContext,
    ImageIntent,
    ImageRouter,
)
from .vision import VisionClassifier, VisionQuestion

# Image cogs subclass this; it is just the generic processor cog.
ImageProcessorCog = ProcessorCog

__all__ = [
    "LEVEL_MESSAGE",
    "LEVEL_FILE",
    "LEVEL_IMAGE",
    "Candidate",
    "Intent",
    "RouterContext",
    "MessageRouter",
    "FileCandidate",
    "FileContext",
    "FileIntent",
    "FileRouter",
    "IMAGE_EXTENSIONS",
    "ImageCandidate",
    "ImageContext",
    "ImageIntent",
    "ImageRouter",
    "VisionClassifier",
    "VisionQuestion",
    "ProcessorCog",
    "ImageProcessorCog",
]
