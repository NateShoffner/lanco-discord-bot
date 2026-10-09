"""An image embed is a downloadable attachment like any other.

`download_attachments` collected URLs from attachments, but for embeds it only
ever appended the tenor-gif special case: a plain image embed assigned `url`
and dropped it, and an embed with neither an image nor a video left `url`
unbound, so the trailing log line raised UnboundLocalError. Every caller
(`hotdog`, `describe`, `AIDetection`, `sleepcheck`) sees that as the image
silently not existing, or as a crash.
"""

import os
from types import SimpleNamespace

import pytest
from utils.file_downloader import FileDownloader

TENOR_PROXY = (
    "https://images-ext-2.discordapp.net/external/abc123/https/"
    "media.tenor.com/M0DJo6-jF7AAAAPo/anime-responsibilities.mp4"
)


def _message(attachments=(), embeds=()):
    return SimpleNamespace(attachments=list(attachments), embeds=list(embeds))


def _embed(image_url=None, video_url=None):
    return SimpleNamespace(
        image=SimpleNamespace(proxy_url=image_url) if image_url else None,
        video=SimpleNamespace(proxy_url=video_url) if video_url else None,
    )


@pytest.fixture
def downloader(monkeypatch, tmp_path):
    """A FileDownloader whose download_file records the URL and writes a stub."""
    dl = FileDownloader()
    dl.requested = []

    async def fake_download_file(url, dir, filename=None):
        dl.requested.append(url)
        path = os.path.join(str(tmp_path), f"file{len(dl.requested)}")
        open(path, "wb").close()
        return path

    monkeypatch.setattr(dl, "download_file", fake_download_file)
    return dl


@pytest.mark.asyncio
async def test_plain_image_embed_is_downloaded(downloader, tmp_path):
    message = _message(embeds=[_embed(image_url="https://i.imgur.com/a.png")])

    results = await downloader.download_attachments(message, str(tmp_path))

    assert downloader.requested == ["https://i.imgur.com/a.png"]
    assert [r.url for r in results] == ["https://i.imgur.com/a.png"]


@pytest.mark.asyncio
async def test_embed_with_nothing_downloadable_returns_empty(downloader, tmp_path):
    """Used to raise UnboundLocalError on the log line below the loop."""
    message = _message(embeds=[_embed()])

    results = await downloader.download_attachments(message, str(tmp_path))

    assert results == []
    assert downloader.requested == []


@pytest.mark.asyncio
async def test_tenor_video_embed_still_rewrites_to_the_gif(downloader, tmp_path):
    message = _message(embeds=[_embed(video_url=TENOR_PROXY)])

    await downloader.download_attachments(message, str(tmp_path))

    assert downloader.requested == ["https://c.tenor.com/M0DJo6-jF7AAAAAC/tenor.gif"]


@pytest.mark.asyncio
async def test_tenor_video_wins_over_its_still_preview(downloader, tmp_path):
    message = _message(
        embeds=[
            _embed(image_url="https://media.tenor.com/still.png", video_url=TENOR_PROXY)
        ]
    )

    await downloader.download_attachments(message, str(tmp_path))

    assert downloader.requested == ["https://c.tenor.com/M0DJo6-jF7AAAAAC/tenor.gif"]


@pytest.mark.asyncio
async def test_attachments_take_precedence_over_embeds(downloader, tmp_path):
    message = _message(
        attachments=[SimpleNamespace(url="https://cdn.discordapp.com/a.png")],
        embeds=[_embed(image_url="https://i.imgur.com/a.png")],
    )

    await downloader.download_attachments(message, str(tmp_path))

    assert downloader.requested == ["https://cdn.discordapp.com/a.png"]


@pytest.mark.asyncio
async def test_a_failed_download_is_not_reported_as_a_file(monkeypatch, tmp_path):
    """download_file returns None on a non-200, which callers then open()."""
    dl = FileDownloader()

    async def failing_download(url, dir, filename=None):
        return None

    monkeypatch.setattr(dl, "download_file", failing_download)
    message = _message(embeds=[_embed(image_url="https://i.imgur.com/gone.png")])

    assert await dl.download_attachments(message, str(tmp_path)) == []
