import asyncio
import ipaddress
import logging
import os
import socket
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

import aiofiles
import aiohttp
from aiohttp.abc import AbstractResolver
from discord import Message
from yarl import URL


class UnsafeUrlError(Exception):
    """A URL was rejected by the guarded fetch."""


DEFAULT_TIMEOUT = 15  # whole request, including connect and read
DEFAULT_MAX_BYTES = 25 * 1024 * 1024
DEFAULT_MAX_REDIRECTS = 5
_ALLOWED_SCHEMES = frozenset({"http", "https"})
_CHUNK_SIZE = 64 * 1024


def is_public_address(ip: str) -> bool:
    """True only for an address that routes on the public internet."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    # ::ffff:127.0.0.1 is loopback, but only the mapped v4 form says so
    if addr.version == 6 and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


async def _resolve_public_addresses(host: str, port: int) -> list[str]:
    """Resolve a host, keeping only its publicly routable addresses."""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            host, port, type=socket.SOCK_STREAM
        )
    except socket.gaierror as e:
        raise UnsafeUrlError(f"could not resolve {host}") from e
    return [info[4][0] for info in infos if is_public_address(info[4][0])]


async def assert_url_is_fetchable(url: str) -> None:
    """Reject anything that is not an http(s) URL on a publicly routable host."""
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeUrlError(f"scheme {parsed.scheme!r} is not allowed")
    host = parsed.hostname
    if not host:
        raise UnsafeUrlError(f"no host in {url!r}")

    # a literal needs no DNS, and aiohttp skips the resolver for one
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not is_public_address(host):
            raise UnsafeUrlError(f"{host} is not a public address")
        return

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if not await _resolve_public_addresses(host, port):
        raise UnsafeUrlError(f"{host} does not resolve to a public address")


class PublicOnlyResolver(AbstractResolver):
    """Drops non-public addresses at connect time, closing the rebinding window
    the pre-flight check leaves open.
    """

    def __init__(self) -> None:
        self._inner = aiohttp.DefaultResolver()

    async def resolve(
        self, host: str, port: int = 0, family: socket.AddressFamily = socket.AF_INET
    ) -> list[dict]:
        results = await self._inner.resolve(host, port, family)
        allowed = [r for r in results if is_public_address(r["host"])]
        if not allowed:
            raise UnsafeUrlError(f"{host} does not resolve to a public address")
        return allowed

    async def close(self) -> None:
        await self._inner.close()


@dataclass
class GuardedResponse:
    """The body of a completed guarded fetch, already fully read."""

    url: str
    status: int
    data: bytes
    content_type: str = None
    charset: str = None

    def text(self) -> str:
        return self.data.decode(self.charset or "utf-8", errors="replace")


async def guarded_fetch(
    url: str,
    *,
    headers: dict = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
) -> GuardedResponse:
    """GET a URL under SSRF, size, and time limits.

    Redirects are followed by hand so every hop is re-checked.
    """
    connector = aiohttp.TCPConnector(resolver=PublicOnlyResolver())
    async with aiohttp.ClientSession(
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=timeout),
        connector=connector,
    ) as session:
        current = url
        for _ in range(max_redirects + 1):
            await assert_url_is_fetchable(current)
            async with session.get(current, allow_redirects=False) as response:
                if response.status in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location")
                    if not location:
                        raise UnsafeUrlError(
                            f"redirect from {current} with no Location"
                        )
                    current = str(URL(current).join(URL(location)))
                    continue

                declared = response.content_length
                if declared is not None and declared > max_bytes:
                    raise UnsafeUrlError(
                        f"{current} declares {declared} bytes, over the "
                        f"{max_bytes} byte cap"
                    )

                chunks = []
                total = 0
                async for chunk in response.content.iter_chunked(_CHUNK_SIZE):
                    total += len(chunk)
                    if total > max_bytes:
                        raise UnsafeUrlError(
                            f"{current} exceeded the {max_bytes} byte cap"
                        )
                    chunks.append(chunk)

                return GuardedResponse(
                    url=current,
                    status=response.status,
                    data=b"".join(chunks),
                    content_type=response.content_type,
                    charset=response.charset,
                )
    raise UnsafeUrlError(f"{url} redirected more than {max_redirects} times")


class Attatchment:
    """Represents a downloaded attachment"""

    def __init__(self, url: str, filename: str):
        self.url = url
        self.filename = filename


class FileDownloader:
    """Download files from the internet"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def get_random_filename(self, url: str, dir: str) -> str:
        """Get a random filename based on the URL"""
        random_uuid = uuid.uuid4()
        ext = url.split(".")[-1].split("?")[0]
        random_filename = os.path.join(dir, f"{random_uuid}.{ext}")
        return random_filename

    async def download_file(self, url: str, dir: str, filename: str = None) -> str:
        """Download a file from a URL"""
        response = await guarded_fetch(url)
        if response.status != 200:
            self.logger.warning(f"HTTP {response.status} downloading {url}")
            return None

        await asyncio.to_thread(os.makedirs, dir, exist_ok=True)

        if not filename:
            filename = self.get_random_filename(url, dir)
        else:
            filename = os.path.join(dir, filename)

        async with aiofiles.open(filename, "wb") as f:
            await f.write(response.data)

        return filename

    async def download_attachments(
        self, message: Message, dir: str
    ) -> list[Attatchment]:
        """Download attachments from a message"""
        local_files = []
        urls = []
        if message.attachments:
            self.logger.info("Attachments found in message")
            for a in message.attachments:
                urls.append(a.url)
        elif message.embeds:
            self.logger.info("Embed found in message")
            for embed in message.embeds:
                # video wins: for tenor the image is just the still preview
                if embed.video and embed.video.proxy_url:
                    proxy_url = embed.video.proxy_url

                    self.logger.info(f"Proxy URL: {proxy_url}")

                    if "tenor.com" in proxy_url:
                        # tenor seems to ignore the extension but instead uses the URL path to determine the file type

                        # gif
                        # https://media.tenor.com/jv1uzXK_ELwAAAAC/fullmetal-alchemist.gif
                        # mp4
                        # https://media.tenor.com/jv1uzXK_ELwAAAPo/fullmetal-alchemist.gif

                        # mp4
                        # https://media.tenor.com/M0DJo6-jF7AAAAPo/anime-responsibilities.mp4
                        # gif
                        # https://media.tenor.com/M0DJo6-jF7AAAAAC/anime-responsibilities.gif

                        # hacky way to get the original url and get the original GIF
                        # Ex: https://images-ext-2.discordapp.net/external/PHVkBmSMxJdxhSl2dlVt9_VL4tiHyn0blDb9ZBNWLjQ/https/media.tenor.com/M0DJo6-jF7AAAAPo/anime-responsibilities.mp4

                        # parse the proxy url and replace the extension, subdomain, and path
                        tenor_url = proxy_url.split("/https/")[1]
                        url_split = tenor_url.split("/")
                        path = url_split[1]
                        if path.endswith("Po"):
                            path = path[:-2] + "AC"
                        urls.append(f"https://c.tenor.com/{path}/tenor.gif")

                        # https://media.tenor.com/jv1uzXK_ELwAAAPo/fullmetal-alchemist.mp4
                        # https://c.tenor.com/jv1uzXK_ELwAAAAC/tenor.gif
                        # https://c.tenor.com/jv1uzXK_ELwAAAC/fullmetal-alchemist.gif
                elif embed.image and embed.image.proxy_url:
                    urls.append(embed.image.proxy_url)
            self.logger.info(f"{len(urls)} downloadable url(s) found in embeds")

        await asyncio.to_thread(os.makedirs, dir, exist_ok=True)

        for url in urls:
            filename = await self.download_file(url, dir)
            if not filename:
                continue
            local_files.append(Attatchment(url, filename))

        return local_files
