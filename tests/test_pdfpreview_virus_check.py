"""PDFPreviewConfig.virus_check must actually gate the VirusTotal upload.

The column existed with a default of True, but post_preview() called
self.virus_check.check_file() unconditionally and never read it - every
previewed PDF, including a private one in a guild that had explicitly tried
to turn it off, was uploaded to a third party with no way to opt out (there
was not even a command to flip the flag). This covers both halves of the fix:
the flag is now read, and a /pdf viruscheck command exists to set it.
"""

import os
import tempfile
from types import SimpleNamespace

import pytest
from cogs.pdfpreview.models import PDFPreviewConfig
from cogs.pdfpreview.pdfpreview import PDFPreview

from tests.test_bot import test_db  # noqa: F401  (fixture)

GUILD_ID = 1001

pytestmark = pytest.mark.asyncio


class _FakeMessage:
    def __init__(self):
        self.guild = SimpleNamespace(id=GUILD_ID)
        self.sent = []

        async def send(**kwargs):
            msg = SimpleNamespace(edits=[])

            async def edit(**edit_kwargs):
                msg.edits.append(edit_kwargs)

            msg.edit = edit
            self.sent.append(kwargs)
            return msg

        self.channel = SimpleNamespace(send=send)


def make_ctx():
    message = _FakeMessage()
    candidate = SimpleNamespace(filename=None, url="https://example.invalid/x.pdf")
    return SimpleNamespace(message=message, candidate=candidate)


@pytest.fixture(autouse=True)
def tables(test_db):
    test_db.create_tables([PDFPreviewConfig])


@pytest.fixture
def cog(test_db, tmp_path, monkeypatch):
    monkeypatch.setattr(
        PDFPreview,
        "get_cog_data_directory",
        lambda self: str(tmp_path),
    )
    bot = SimpleNamespace(database=test_db)
    instance = PDFPreview(bot)

    # A real file: discord.File opens whatever path it is given, and
    # build_preview_embeds only emits the metadata fields (where the
    # VirusTotal field lives) for index 0 of a non-empty image_paths.
    fake_page = os.path.join(tmp_path, "doc_page1.png")
    with open(fake_page, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
    instance.generate_pdf_preview = lambda path, pages: ([fake_page], 1)

    calls = []

    async def fake_check_file(path):
        calls.append(path)
        return SimpleNamespace(is_safe=True, url="https://virustotal.invalid/x")

    instance.virus_check = SimpleNamespace(check_file=fake_check_file)
    instance._virus_check_calls = calls
    return instance


def make_pdf_file(tmp_path) -> str:
    path = os.path.join(tmp_path, "doc.pdf")
    with open(path, "wb") as f:
        f.write(b"%PDF-1.4\n")
    return path


async def test_post_preview_skips_virustotal_when_disabled(cog, tmp_path):
    PDFPreviewConfig.create(guild_id=GUILD_ID, enabled=True, virus_check=False)
    ctx = make_ctx()
    ctx.candidate.filename = make_pdf_file(tmp_path)

    await cog.post_preview(ctx)

    assert cog._virus_check_calls == []
    sent_embed = ctx.message.sent[0]["embeds"][0]
    field_names = [f.name for f in sent_embed.fields]
    assert "VirusTotal Results" not in field_names


async def test_post_preview_runs_virustotal_by_default(cog, tmp_path):
    # No config row at all: the model's own default (True) applies.
    ctx = make_ctx()
    ctx.candidate.filename = make_pdf_file(tmp_path)

    await cog.post_preview(ctx)

    assert cog._virus_check_calls == [ctx.candidate.filename]
    sent_embed = ctx.message.sent[0]["embeds"][0]
    field_names = [f.name for f in sent_embed.fields]
    assert "VirusTotal Results" in field_names


async def test_viruscheck_command_toggles_the_flag(cog):
    interaction = SimpleNamespace(
        guild=SimpleNamespace(id=GUILD_ID),
        response=SimpleNamespace(messages=[]),
    )

    async def send_message(content=None, **kwargs):
        interaction.response.messages.append(content)

    interaction.response.send_message = send_message

    await PDFPreview.viruscheck.callback(cog, interaction)
    config = PDFPreviewConfig.get(guild_id=GUILD_ID)
    assert config.virus_check is False

    await PDFPreview.viruscheck.callback(cog, interaction)
    config = PDFPreviewConfig.get(guild_id=GUILD_ID)
    assert config.virus_check is True
