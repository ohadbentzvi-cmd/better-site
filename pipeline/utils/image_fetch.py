"""SSRF-checked, size-capped image fetcher.

Used by the Extractor (html_only strategy and the vision/hybrid variants
when they need raw image bytes) to pull logo and hero candidates off the
lead's website. Safety constraints, in order of priority:

1. Every URL in the redirect chain is SSRF-checked before the request —
   not just the entry URL. A 302 to ``http://169.254.169.254/...`` would
   otherwise sneak past the entry-point check.
2. The response body is streamed and aborted as soon as cumulative bytes
   exceed :data:`MAX_IMAGE_BYTES`, so a malicious or pathological server
   cannot exhaust memory.
3. Only ``image/*`` content-types are accepted; everything else raises
   :class:`NotAnImageError`.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog

from pipeline.utils.ssrf import assert_safe_url

log = structlog.get_logger(__name__)

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_REDIRECTS = 5
HTTP_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
REQUEST_HEADERS = {
    "User-Agent": "BetterSiteExtractor/0.1 (+https://bettersite.co/bot)",
    "Accept": "image/*",
}

_EXT_BY_CONTENT_TYPE: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/svg+xml": "svg",
    "image/x-icon": "ico",
    "image/vnd.microsoft.icon": "ico",
    "image/avif": "avif",
}


class ImageFetchError(Exception):
    """Base class for image-fetch failures."""


class TooManyRedirectsError(ImageFetchError):
    """Redirect chain exceeded :data:`MAX_REDIRECTS`."""


class MalformedRedirectError(ImageFetchError):
    """Server returned a 3xx without a usable ``Location`` header."""


class NotAnImageError(ImageFetchError):
    """Response ``Content-Type`` is missing or not ``image/*``."""


class ImageTooLargeError(ImageFetchError):
    """Declared or streamed body exceeded :data:`MAX_IMAGE_BYTES`."""


@dataclass(frozen=True)
class FetchedImage:
    """Result of a successful :func:`fetch_image` call."""

    url: str
    body: bytes
    content_type: str
    extension: str


def _ext_from_content_type(content_type: str) -> str:
    if content_type in _EXT_BY_CONTENT_TYPE:
        return _EXT_BY_CONTENT_TYPE[content_type]
    subtype = content_type.split("/", 1)[1].split("+", 1)[0]
    cleaned = "".join(c for c in subtype if c.isalnum())
    return cleaned or "bin"


def fetch_image(url: str) -> FetchedImage:
    """Fetch an image with SSRF + size + content-type guards.

    Follows up to :data:`MAX_REDIRECTS` hops, calling
    :func:`pipeline.utils.ssrf.assert_safe_url` before each one. The body
    is streamed so the worker never materializes more than
    :data:`MAX_IMAGE_BYTES`.

    Raises:
        UnsafeUrlError: any URL in the redirect chain failed SSRF.
        TooManyRedirectsError: redirect chain too long.
        MalformedRedirectError: 3xx response with no Location.
        NotAnImageError: response Content-Type is not image/*.
        ImageTooLargeError: declared or streamed body exceeded the cap.
        httpx.HTTPError: transport, status, or decode errors from httpx.
    """
    current = url
    with httpx.Client(
        headers=REQUEST_HEADERS, timeout=HTTP_TIMEOUT, follow_redirects=False
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            assert_safe_url(current)
            with client.stream("GET", current) as resp:
                if resp.is_redirect:
                    location = resp.headers.get("location")
                    if not location:
                        raise MalformedRedirectError(
                            f"3xx without Location header for {current!r}"
                        )
                    current = str(httpx.URL(current).join(location))
                    continue

                resp.raise_for_status()
                return _consume(resp, current)

    raise TooManyRedirectsError(
        f"redirect chain exceeded {MAX_REDIRECTS} hops starting from {url!r}"
    )


def _consume(resp: httpx.Response, final_url: str) -> FetchedImage:
    content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
    if not content_type.startswith("image/"):
        raise NotAnImageError(
            f"non-image content-type {content_type!r} for {final_url!r}"
        )

    declared = resp.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > MAX_IMAGE_BYTES:
        raise ImageTooLargeError(
            f"declared content-length {declared} exceeds {MAX_IMAGE_BYTES} for {final_url!r}"
        )

    buf = bytearray()
    for chunk in resp.iter_bytes():
        buf.extend(chunk)
        if len(buf) > MAX_IMAGE_BYTES:
            raise ImageTooLargeError(
                f"streamed body exceeded {MAX_IMAGE_BYTES} bytes for {final_url!r}"
            )

    return FetchedImage(
        url=final_url,
        body=bytes(buf),
        content_type=content_type,
        extension=_ext_from_content_type(content_type),
    )


__all__ = [
    "FetchedImage",
    "ImageFetchError",
    "ImageTooLargeError",
    "MAX_IMAGE_BYTES",
    "MAX_REDIRECTS",
    "MalformedRedirectError",
    "NotAnImageError",
    "TooManyRedirectsError",
    "fetch_image",
]
