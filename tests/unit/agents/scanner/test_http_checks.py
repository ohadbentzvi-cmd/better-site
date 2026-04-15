"""Unit tests for the parser helpers inside the HTTP check module."""

from __future__ import annotations

from pipeline.agents.scanner.checks.http import _robots_blocks_all


class TestRobotsBlocksAll:
    def test_empty_is_not_blocking(self) -> None:
        assert _robots_blocks_all("") is False

    def test_star_disallow_root_blocks_all(self) -> None:
        body = "User-agent: *\nDisallow: /\n"
        assert _robots_blocks_all(body) is True

    def test_specific_ua_disallow_root_does_not_block_all(self) -> None:
        body = "User-agent: BadBot\nDisallow: /\n"
        assert _robots_blocks_all(body) is False

    def test_star_allow_everything(self) -> None:
        body = "User-agent: *\nAllow: /\n"
        assert _robots_blocks_all(body) is False

    def test_star_disallow_subpath_does_not_block_all(self) -> None:
        body = "User-agent: *\nDisallow: /admin\n"
        assert _robots_blocks_all(body) is False

    def test_comments_ignored(self) -> None:
        body = "# my robots\nUser-agent: *\n# block everything\nDisallow: /\n"
        assert _robots_blocks_all(body) is True

    def test_case_insensitive(self) -> None:
        body = "USER-AGENT: *\nDISALLOW: /\n"
        assert _robots_blocks_all(body) is True
