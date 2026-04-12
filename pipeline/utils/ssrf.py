"""SSRF protection for lead-supplied URLs.

Every code path that makes an HTTP request against a lead-supplied URL
must call ``assert_safe_url(url)`` before the request. Raises
``UnsafeUrlError`` if the URL resolves to a non-public destination.

Blocks:
- Non-http(s) schemes (file://, gopher://, ftp://, etc.)
- RFC1918 private ranges (10/8, 172.16/12, 192.168/16)
- Link-local (169.254/16) — includes cloud metadata at 169.254.169.254
- Loopback (127/8, ::1)
- Carrier-grade NAT (100.64/10)
- IPv6 unique-local (fc00::/7)
- IPv6 link-local (fe80::/10)

This intentionally does not block by domain name — a domain can resolve to
a private IP, so we resolve and inspect the actual address.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeUrlError(ValueError):
    """Raised when a URL cannot be safely fetched."""


ALLOWED_SCHEMES = frozenset({"http", "https"})


def _is_public_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def assert_safe_url(url: str) -> None:
    """Raise UnsafeUrlError if the URL cannot be safely fetched.

    Call this BEFORE every HTTP request or Playwright navigation against a
    lead-supplied URL.
    """
    parsed = urlparse(url)

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeUrlError(f"disallowed scheme: {parsed.scheme!r}")

    host = parsed.hostname
    if not host:
        raise UnsafeUrlError("missing hostname")

    # Resolve all A/AAAA records and verify every one is public.
    try:
        addr_info = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise UnsafeUrlError(f"DNS resolution failed for {host!r}") from e

    for info in addr_info:
        ip_str = info[4][0]
        if not _is_public_ip(ip_str):
            raise UnsafeUrlError(
                f"host {host!r} resolves to non-public address {ip_str}"
            )
