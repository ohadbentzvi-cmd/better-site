"""URL helpers: canonicalization for dedup, safe fetch prep."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

import tldextract


def canonicalize_domain(url: str) -> str:
    """Return a canonical domain form suitable for unique-dedup.

    - Lowercase
    - Strip ``www.`` subdomain
    - Drop path, query, fragment

    >>> canonicalize_domain("https://WWW.Acme-Movers.com/about?utm=x")
    'acme-movers.com'
    >>> canonicalize_domain("acme-movers.com/")
    'acme-movers.com'
    """
    if "://" not in url:
        url = "https://" + url
    ext = tldextract.extract(url)
    if not ext.domain or not ext.suffix:
        # Fallback: just lowercase the hostname portion
        parsed = urlparse(url)
        return (parsed.hostname or url).lower()
    return f"{ext.domain}.{ext.suffix}".lower()


def canonicalize_url(url: str) -> str:
    """Return a normalized URL form (adds https, lowercases host, strips fragment)."""
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.port:
        host = f"{host}:{parsed.port}"
    path = parsed.path or "/"
    return urlunparse(
        (
            parsed.scheme.lower(),
            host,
            path,
            parsed.params,
            parsed.query,
            "",  # drop fragment
        )
    )
