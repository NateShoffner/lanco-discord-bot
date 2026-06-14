"""File router: extracts downloadable attachments and fetches each once.

Adds the ``file`` level to ``MessageRouter``. A ``FileCandidate`` carries a URL
and, after ``_prepare``, the downloaded bytes and local path shared across all
file/image intents for that attachment.
"""

from __future__ import annotations

import logging
import mimetypes
import os
import re
from dataclasses import dataclass
from typing import Optional

import discord
from utils.file_downloader import FileDownloader

from .base import (
    LEVEL_FILE,
    LEVEL_MESSAGE,
    Candidate,
    Intent,
    MessageRouter,
    RouterContext,
)

logger = logging.getLogger(__name__)

# Bare http(s) links in message content that point at a file (have a path
# segment ending in an extension). Query strings are tolerated.
_FILE_URL_RE = re.compile(r"https?://\S+/[^/\s?#]+\.[a-zA-Z0-9]{1,8}(?:\?\S*)?")


@dataclass
class FileCandidate(Candidate):
    url: str = ""
    content_type: Optional[str] = None
    size: Optional[int] = None
    source: str = "attachment"  # "attachment" | "embed"
    filename: Optional[str] = None  # local path, set after download
    data: Optional[bytes] = None  # raw bytes, set after download

    def __post_init__(self) -> None:
        self.level = LEVEL_FILE

    @property
    def extension(self) -> str:
        tail = self.url.split("?")[0].rsplit(".", 1)
        return tail[-1].lower() if len(tail) == 2 else ""


@dataclass
class FileContext(RouterContext):
    candidate: FileCandidate = None


@dataclass
class FileIntent(Intent):
    def __post_init__(self) -> None:
        self.level = LEVEL_FILE


class FileRouter(MessageRouter):
    LEVELS = (LEVEL_MESSAGE, LEVEL_FILE)

    def __init__(self, bot, cache_dir: str):
        super().__init__(bot)
        self.cache_dir: str = cache_dir
        self.file_downloader: FileDownloader = FileDownloader()

    def _extract_candidates(self, message: discord.Message) -> list[Candidate]:
        candidates = super()._extract_candidates(message)
        seen_urls: set[str] = set()
        for att in message.attachments:
            seen_urls.add(att.url)
            candidates.append(
                self._make_file_candidate(
                    url=att.url,
                    content_type=att.content_type,
                    size=att.size,
                    source="attachment",
                )
            )
        if not message.attachments:
            for embed in message.embeds:
                if embed.image and embed.image.proxy_url:
                    seen_urls.add(embed.image.proxy_url)
                    candidates.append(
                        self._make_file_candidate(
                            url=embed.image.proxy_url, source="embed"
                        )
                    )
        # Bare file links typed in the message body (e.g. a .pdf URL).
        for url in _FILE_URL_RE.findall(message.content or ""):
            if url not in seen_urls:
                seen_urls.add(url)
                candidates.append(self._make_file_candidate(url=url, source="link"))
        return candidates

    def _make_file_candidate(self, **kwargs) -> FileCandidate:
        """Build the candidate for one attachment. ImageRouter overrides this to
        return an ImageCandidate for images, so each attachment yields exactly
        one candidate (downloaded once) that serves both file and image intents.
        """
        return FileCandidate(**kwargs)

    async def _prepare(self, candidate: Candidate) -> bool:
        if not isinstance(candidate, FileCandidate):
            return await super()._prepare(candidate)
        try:
            filename = await self.file_downloader.download_file(
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

    def _build_context(
        self, message: discord.Message, candidate: Candidate
    ) -> RouterContext:
        if isinstance(candidate, FileCandidate):
            return FileContext(message=message, candidate=candidate)
        return super()._build_context(message, candidate)

    def _cleanup(self, candidate: Candidate) -> None:
        if isinstance(candidate, FileCandidate) and candidate.filename:
            if os.path.exists(candidate.filename):
                try:
                    os.remove(candidate.filename)
                except OSError:
                    pass
