"""Sanity tests for pipeline.utils.url."""

from __future__ import annotations

from pipeline.utils.url import canonicalize_domain, canonicalize_url


class TestCanonicalizeDomain:
    def test_strips_www_prefix(self) -> None:
        assert canonicalize_domain("https://www.acme-movers.com") == "acme-movers.com"

    def test_lowercases_host(self) -> None:
        assert canonicalize_domain("https://ACME-Movers.COM") == "acme-movers.com"

    def test_drops_path_query_fragment(self) -> None:
        assert (
            canonicalize_domain("https://acme-movers.com/about?utm=x#top")
            == "acme-movers.com"
        )

    def test_adds_scheme_when_missing(self) -> None:
        assert canonicalize_domain("acme-movers.com") == "acme-movers.com"

    def test_subdomain_collapses_to_registrable(self) -> None:
        assert canonicalize_domain("https://shop.acme-movers.com") == "acme-movers.com"


class TestCanonicalizeUrl:
    def test_adds_https(self) -> None:
        assert canonicalize_url("acme-movers.com").startswith("https://")

    def test_lowercases_host(self) -> None:
        assert "acme-movers.com" in canonicalize_url("https://ACME-Movers.com/")

    def test_drops_fragment(self) -> None:
        assert "#" not in canonicalize_url("https://acme-movers.com/about#section")
