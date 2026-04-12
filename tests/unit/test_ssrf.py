"""Sanity tests for pipeline.utils.ssrf."""

from __future__ import annotations

import pytest

from pipeline.utils.ssrf import UnsafeUrlError, assert_safe_url


class TestAssertSafeUrl:
    def test_rejects_file_scheme(self) -> None:
        with pytest.raises(UnsafeUrlError, match="disallowed scheme"):
            assert_safe_url("file:///etc/passwd")

    def test_rejects_gopher_scheme(self) -> None:
        with pytest.raises(UnsafeUrlError, match="disallowed scheme"):
            assert_safe_url("gopher://evil.example/")

    def test_rejects_missing_host(self) -> None:
        with pytest.raises(UnsafeUrlError):
            assert_safe_url("https://")


class TestPrivateIpDetection:
    """These tests pass a literal IP so they don't depend on DNS."""

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/",
            "http://10.0.0.1/",
            "http://172.16.0.1/",
            "http://192.168.1.1/",
            "http://169.254.169.254/",  # AWS metadata
        ],
    )
    def test_rejects_private_ip(self, url: str) -> None:
        with pytest.raises(UnsafeUrlError, match="non-public"):
            assert_safe_url(url)
