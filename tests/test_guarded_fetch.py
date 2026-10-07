"""Every URL the bot fetches on someone else's say-so goes through the guard.

Three cogs fetch a URL supplied by a user or an admin and put the result back
in chat: `webpreview` echoes the page title, the file router downloads any
.pdf link it sees, and `rssfeed` polls admin-supplied feeds. A bare
`session.get` there is a readable SSRF: a link to 127.0.0.1, to another
container on the Docker network, or to 169.254.169.254 would be fetched and
read out loud, with no size cap and no timeout to stop it.

`utils.file_downloader.guarded_fetch` is the one way in. These tests cover the
host filter, the per-hop redirect re-check, and the body cap, plus a static
check that those three call sites have not quietly gone back to a raw session.
"""

import ast
import os

import pytest
from utils.file_downloader import (
    DEFAULT_MAX_REDIRECTS,
    UnsafeUrlError,
    assert_url_is_fetchable,
    guarded_fetch,
    is_public_address,
)

APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "::1",
        "10.0.0.5",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",  # cloud instance metadata
        "0.0.0.0",
        "224.0.0.1",
        "::ffff:127.0.0.1",  # loopback wearing a v6 hat
        "not-an-ip",
    ],
)
def test_non_public_addresses_are_rejected(ip):
    assert not is_public_address(ip)


@pytest.mark.parametrize("ip", ["93.184.216.34", "8.8.8.8", "2606:4700:4700::1111"])
def test_public_addresses_are_allowed(ip):
    assert is_public_address(ip)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://localhost:8080/",
        "http://[::1]/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/",
        "file:///etc/passwd",
        "gopher://example.com/",
        "http:///nohost",
    ],
)
async def test_assert_url_is_fetchable_rejects(url):
    with pytest.raises(UnsafeUrlError):
        await assert_url_is_fetchable(url)


@pytest.mark.asyncio
async def test_assert_url_is_fetchable_allows_a_public_host(monkeypatch):
    monkeypatch.setattr(
        "utils.file_downloader._resolve_public_addresses",
        _fake_resolver(["93.184.216.34"]),
    )
    await assert_url_is_fetchable("https://example.com/page")


def _fake_resolver(addresses):
    async def resolve(host, port):
        return addresses

    return resolve


class _FakeContent:
    def __init__(self, data: bytes):
        self._data = data

    async def iter_chunked(self, size: int):
        for start in range(0, len(self._data), size):
            yield self._data[start : start + size]


class _FakeResponse:
    def __init__(self, status=200, headers=None, data=b"", content_length=None):
        self.status = status
        self.headers = headers or {}
        self.content = _FakeContent(data)
        self.content_length = content_length
        self.content_type = "text/html"
        self.charset = "utf-8"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    """Serves a scripted response per URL and records what was requested."""

    def __init__(self, script):
        self.script = script
        self.requested = []

    def get(self, url, allow_redirects=False):
        self.requested.append(url)
        return self.script[url]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _install_fake_session(monkeypatch, script):
    session = _FakeSession(script)
    monkeypatch.setattr(
        "utils.file_downloader.aiohttp.ClientSession", lambda **kw: session
    )
    monkeypatch.setattr("utils.file_downloader.aiohttp.TCPConnector", lambda **kw: None)
    return session


@pytest.mark.asyncio
async def test_redirect_to_a_private_address_is_rejected(monkeypatch):
    """An open redirector on a public host must not get the bot to localhost."""
    session = _install_fake_session(
        monkeypatch,
        {
            "https://example.com/go": _FakeResponse(
                status=302, headers={"Location": "http://169.254.169.254/latest/"}
            )
        },
    )
    monkeypatch.setattr(
        "utils.file_downloader._resolve_public_addresses",
        _fake_resolver(["93.184.216.34"]),
    )

    with pytest.raises(UnsafeUrlError):
        await guarded_fetch("https://example.com/go")

    # the first hop was fetched, the metadata endpoint never was
    assert session.requested == ["https://example.com/go"]


@pytest.mark.asyncio
async def test_redirect_chain_is_bounded(monkeypatch):
    session = _install_fake_session(
        monkeypatch,
        {
            "https://example.com/loop": _FakeResponse(
                status=302, headers={"Location": "https://example.com/loop"}
            )
        },
    )
    monkeypatch.setattr(
        "utils.file_downloader._resolve_public_addresses",
        _fake_resolver(["93.184.216.34"]),
    )

    with pytest.raises(UnsafeUrlError):
        await guarded_fetch("https://example.com/loop")
    assert len(session.requested) == DEFAULT_MAX_REDIRECTS + 1


@pytest.mark.asyncio
async def test_declared_oversize_body_is_rejected_before_reading(monkeypatch):
    _install_fake_session(
        monkeypatch,
        {
            "https://example.com/big": _FakeResponse(
                data=b"x" * 10, content_length=999_999
            )
        },
    )
    monkeypatch.setattr(
        "utils.file_downloader._resolve_public_addresses",
        _fake_resolver(["93.184.216.34"]),
    )

    with pytest.raises(UnsafeUrlError):
        await guarded_fetch("https://example.com/big", max_bytes=1024)


@pytest.mark.asyncio
async def test_body_over_the_cap_is_rejected_while_streaming(monkeypatch):
    """A lying or absent Content-Length still cannot blow up memory."""
    _install_fake_session(
        monkeypatch,
        {"https://example.com/big": _FakeResponse(data=b"x" * 500_000)},
    )
    monkeypatch.setattr(
        "utils.file_downloader._resolve_public_addresses",
        _fake_resolver(["93.184.216.34"]),
    )

    with pytest.raises(UnsafeUrlError):
        await guarded_fetch("https://example.com/big", max_bytes=1024)


@pytest.mark.asyncio
async def test_a_normal_body_comes_back_decoded(monkeypatch):
    _install_fake_session(
        monkeypatch,
        {"https://example.com/": _FakeResponse(data=b"<title>hi</title>")},
    )
    monkeypatch.setattr(
        "utils.file_downloader._resolve_public_addresses",
        _fake_resolver(["93.184.216.34"]),
    )

    response = await guarded_fetch("https://example.com/")
    assert response.status == 200
    assert response.text() == "<title>hi</title>"


# The modules whose fetches are reachable by a URL someone else chose.
_GUARDED_MODULES = [
    "utils/file_downloader.py",
    "cogs/webpreview/webpreview.py",
    "cogs/rssfeed/rssfeed.py",
]


def test_url_fetching_modules_do_not_open_a_raw_session():
    """aiohttp.ClientSession is the bypass; guarded_fetch owns the only one."""
    offenders = []
    for rel in _GUARDED_MODULES:
        path = os.path.join(APP_DIR, *rel.split("/"))
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name == "guarded_fetch":
                continue
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                func = inner.func
                if isinstance(func, ast.Attribute) and func.attr == "ClientSession":
                    offenders.append(f"{rel}:{inner.lineno} ({node.name})")
    assert not offenders, "unguarded aiohttp session in a URL fetcher:\n" + "\n".join(
        offenders
    )
