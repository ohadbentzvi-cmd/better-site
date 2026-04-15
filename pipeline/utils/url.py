"""URL canonicalization + canonical-domain extraction.

Every code path that persists a website URL goes through
``canonicalize_url`` (for the storage form) and ``canonicalize_domain``
(for dedup). Source-agnostic by design — BBB, FMCSA, GMB, whatever.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit, urlunsplit

import tldextract

# RFC 3986 scheme: ALPHA *( ALPHA / DIGIT / "+" / "-" / "." )
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+\-.]*:", re.ASCII)

_TRACKING_PARAM_PREFIXES = ("utm_",)
_TRACKING_PARAMS = frozenset(
    {
        "gclid", "fbclid", "mc_cid", "mc_eid", "yclid", "dclid", "msclkid",
        "ref", "referrer", "trk",
    }
)


class InvalidURLError(ValueError):
    """Raised when a URL cannot be canonicalized."""


def canonicalize_url(raw: str) -> str:
    """Normalize a URL to a stable storage form.

    - Lowercase scheme + host
    - Strip ``www.`` from host
    - Strip default ports (80/443)
    - Drop the fragment
    - Drop tracking query params (utm_*, gclid, fbclid, …)
    - Sort remaining query params for determinism
    - Collapse a bare ``/`` path to empty (so ``example.com/`` and ``example.com``
      both canonicalize identically).

    Raises ``InvalidURLError`` for empty, schemeless, or non-http(s) input.

    >>> canonicalize_url("https://WWW.EXAMPLE.COM/foo/?utm_source=bbb#top")
    'https://example.com/foo/'
    >>> canonicalize_url("http://Example.com/")
    'http://example.com'
    """
    if not raw or not raw.strip():
        raise InvalidURLError("empty URL")
    raw = raw.strip()
    # Only prepend https:// when the string is a bare domain with no scheme at
    # all. "javascript:alert(1)" has a scheme, so it must fail the scheme check
    # below rather than being coerced into "https://javascript:alert(1)".
    if not _SCHEME_RE.match(raw):
        raw = "https://" + raw
    try:
        parts = urlsplit(raw)
    except ValueError as e:
        raise InvalidURLError(f"cannot parse URL: {raw!r}") from e
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise InvalidURLError(f"unsupported scheme: {scheme!r}")
    host = parts.hostname
    if not host:
        raise InvalidURLError(f"no host in URL: {raw!r}")
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]

    netloc = host
    if parts.port:
        is_default_port = (
            (scheme == "http" and parts.port == 80)
            or (scheme == "https" and parts.port == 443)
        )
        if not is_default_port:
            netloc = f"{host}:{parts.port}"

    kept_query = sorted(
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not _is_tracking_param(k)
    )
    query = urlencode(kept_query, doseq=True)

    path = parts.path or ""
    if path == "/":
        path = ""
    # When a query is present we need at least a "/" before it; bare
    # "https://host?q=1" is legal but ugly and some clients normalize it anyway.
    if not path and query:
        path = "/"

    return urlunsplit((scheme, netloc, path, query, ""))


def canonicalize_domain(url: str) -> str:
    """Return the registrable domain for dedup (handles multi-part TLDs).

    Accepts raw user input or a pre-canonicalized URL.

    >>> canonicalize_domain("https://WWW.Acme-Movers.com/about?utm=x")
    'acme-movers.com'
    >>> canonicalize_domain("shop.example.co.uk/")
    'example.co.uk'
    """
    if not url or not url.strip():
        raise InvalidURLError("empty URL")
    url = url.strip()
    if not _SCHEME_RE.match(url):
        url = "https://" + url
    ext = tldextract.extract(url)
    if not ext.domain or not ext.suffix:
        # Fallback: bare hostname. Covers IP literals + internal hosts,
        # which the SSRF check will reject downstream anyway.
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host:
            raise InvalidURLError(f"cannot extract domain from {url!r}")
        return host
    return f"{ext.domain}.{ext.suffix}".lower()


# Back-compat alias; earlier code imported this name.
extract_canonical_domain = canonicalize_domain


def _is_tracking_param(key: str) -> bool:
    k = key.lower()
    return k in _TRACKING_PARAMS or any(k.startswith(p) for p in _TRACKING_PARAM_PREFIXES)


__all__ = [
    "InvalidURLError",
    "canonicalize_url",
    "canonicalize_domain",
    "extract_canonical_domain",
]
