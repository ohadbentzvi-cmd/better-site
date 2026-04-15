"""HTTP checks: robots.txt / llms.txt / sitemap(s) / security headers.

All four sub-checks fire in parallel via ``asyncio.gather``; none of
them need a real browser. Each sub-check degrades gracefully — a
failed fetch maps to "not present" or default security-false.
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
import structlog

from pipeline.agents.scanner.base import HttpCheckResult

log = structlog.get_logger(__name__)

HTTP_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
REQUEST_HEADERS = {
    "User-Agent": "BetterSiteScanner/0.1 (+https://bettersite.co/bot)",
    "Accept": "*/*",
}
SITEMAP_CANDIDATES = ("/sitemap.xml", "/sitemap_index.xml")


async def fetch_http_checks(url: str) -> HttpCheckResult:
    base = _origin(url)
    if base is None:
        return HttpCheckResult(available=False, error_reason=f"bad URL: {url}")

    async with httpx.AsyncClient(
        headers=REQUEST_HEADERS, timeout=HTTP_TIMEOUT, follow_redirects=True
    ) as client:
        robots, llms, sitemap, headers = await asyncio.gather(
            _check_robots(client, base),
            _check_llms(client, base),
            _check_sitemap(client, base),
            _check_security_headers(client, url),
            return_exceptions=True,
        )

    result = HttpCheckResult()
    if isinstance(robots, dict):
        result.robots_present = robots.get("present", False)
        result.robots_blocks_all = robots.get("blocks_all", False)
    if isinstance(llms, bool):
        result.llms_txt_present = llms
    if isinstance(sitemap, dict):
        result.sitemap_present = sitemap.get("present", False)
        result.sitemap_url_count = sitemap.get("url_count", 0)
    if isinstance(headers, dict):
        result.has_hsts = headers.get("hsts", False)
        result.has_csp = headers.get("csp", False)
        result.has_x_frame_options = headers.get("x_frame_options", False)
        result.has_x_content_type_options = headers.get("x_content_type_options", False)
        result.has_referrer_policy = headers.get("referrer_policy", False)
    return result


def _origin(url: str) -> str | None:
    """Return ``scheme://host[:port]`` with no path/query."""
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return None
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


async def _check_robots(client: httpx.AsyncClient, base: str) -> dict[str, bool]:
    try:
        r = await client.get(urljoin(base, "/robots.txt"))
    except httpx.HTTPError as e:
        log.info("http.robots.error", base=base, error=str(e))
        return {"present": False, "blocks_all": False}
    if r.status_code != 200 or not r.text.strip():
        return {"present": False, "blocks_all": False}
    return {
        "present": True,
        "blocks_all": _robots_blocks_all(r.text),
    }


def _robots_blocks_all(body: str) -> bool:
    """True if a ``User-agent: *`` block has a bare ``Disallow: /``."""
    lines = [line.strip() for line in body.splitlines() if line.strip() and not line.strip().startswith("#")]
    in_star_block = False
    for line in lines:
        if re.match(r"(?i)^user-agent\s*:\s*\*\s*$", line):
            in_star_block = True
            continue
        if re.match(r"(?i)^user-agent\s*:", line):
            in_star_block = False
            continue
        if in_star_block and re.match(r"(?i)^disallow\s*:\s*/\s*$", line):
            return True
    return False


async def _check_llms(client: httpx.AsyncClient, base: str) -> bool:
    try:
        r = await client.get(urljoin(base, "/llms.txt"))
    except httpx.HTTPError:
        return False
    return r.status_code == 200 and bool(r.text.strip())


async def _check_sitemap(client: httpx.AsyncClient, base: str) -> dict[str, int | bool]:
    for path in SITEMAP_CANDIDATES:
        try:
            r = await client.get(urljoin(base, path))
        except httpx.HTTPError:
            continue
        if r.status_code == 200 and r.text.strip():
            count = len(re.findall(r"<url\b", r.text, flags=re.IGNORECASE))
            return {"present": True, "url_count": count}
    return {"present": False, "url_count": 0}


async def _check_security_headers(client: httpx.AsyncClient, url: str) -> dict[str, bool]:
    try:
        r = await client.get(url)
    except httpx.HTTPError as e:
        log.info("http.security.error", url=url, error=str(e))
        return {}
    h = {k.lower(): v for k, v in r.headers.items()}
    return {
        "hsts": "strict-transport-security" in h,
        "csp": "content-security-policy" in h,
        "x_frame_options": "x-frame-options" in h,
        "x_content_type_options": "x-content-type-options" in h,
        "referrer_policy": "referrer-policy" in h,
    }


__all__ = ["fetch_http_checks"]
