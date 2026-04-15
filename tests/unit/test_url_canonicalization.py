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

    def test_strips_www_prefix(self) -> None:
        assert canonicalize_url("https://www.acme.com") == "https://acme.com"

    def test_collapses_root_slash(self) -> None:
        assert canonicalize_url("https://acme.com/") == canonicalize_url("https://acme.com")

    def test_keeps_non_root_trailing_slash(self) -> None:
        assert canonicalize_url("https://acme.com/services/").endswith("/services/")

    def test_strips_utm_params(self) -> None:
        assert "utm_" not in canonicalize_url("https://acme.com/?utm_source=bbb&x=1")

    def test_keeps_non_tracking_params_sorted(self) -> None:
        assert canonicalize_url("https://acme.com/?b=2&a=1") == "https://acme.com/?a=1&b=2"

    def test_strips_default_http_port(self) -> None:
        assert canonicalize_url("http://acme.com:80/") == "http://acme.com"

    def test_keeps_non_default_port(self) -> None:
        assert canonicalize_url("https://acme.com:8443/") == "https://acme.com:8443"

    def test_rejects_non_http_scheme(self) -> None:
        import pytest
        from pipeline.utils.url import InvalidURLError

        with pytest.raises(InvalidURLError):
            canonicalize_url("javascript:alert(1)")

    def test_rejects_empty(self) -> None:
        import pytest
        from pipeline.utils.url import InvalidURLError

        with pytest.raises(InvalidURLError):
            canonicalize_url("")
