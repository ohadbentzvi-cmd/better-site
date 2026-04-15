"""Scoring function tests — pure, no IO."""

from __future__ import annotations

from pipeline.agents.scanner.base import (
    BrowserCheckResult,
    HttpCheckResult,
    PageSpeedData,
    PageSpeedResult,
)
from pipeline.agents.scanner.scoring import (
    WEIGHT_AI,
    WEIGHT_PERFORMANCE,
    WEIGHT_SECURITY,
    WEIGHT_SEO,
    score_scan,
)


def _perf(
    score: int = 50, lcp: float = 3000, cls: float = 0.05, tbt: float = 150, weight: int = 1_200_000
) -> PageSpeedResult:
    return PageSpeedResult(
        strategy="mobile",
        performance_score=score,
        seo_score=80,
        lcp_ms=lcp,
        cls=cls,
        tbt_ms=tbt,
        page_weight_bytes=weight,
    )


def _full_browser() -> BrowserCheckResult:
    return BrowserCheckResult(
        available=True,
        title="Westheimer Transfer Movers Houston",
        meta_description="Licensed moving company serving Houston for 37 years. Residential and commercial moves.",
        canonical_url="https://example.com/",
        og_title="Westheimer Transfer",
        og_description="Moving company Houston",
        og_image="https://example.com/og.png",
        has_viewport_meta=True,
        h1_count=1,
        h2_count=3,
        h3_count=2,
        heading_hierarchy_ok=True,
        image_count=10,
        images_with_alt=9,
        json_ld_types=["LocalBusiness"],
    )


def _full_http() -> HttpCheckResult:
    return HttpCheckResult(
        available=True,
        robots_present=True,
        robots_blocks_all=False,
        llms_txt_present=True,
        sitemap_present=True,
        sitemap_url_count=42,
        has_hsts=True,
        has_csp=True,
        has_x_frame_options=True,
        has_x_content_type_options=True,
        has_referrer_policy=True,
    )


class TestOverallComposition:
    def test_all_dimensions_available_produces_overall(self) -> None:
        result = score_scan(
            PageSpeedData(mobile=_perf(80), desktop=_perf(80), available=True),
            _full_browser(),
            _full_http(),
        )
        assert result["overall"] is not None
        assert 0 <= result["overall"] <= 100
        assert result["scan_partial"] is False

    def test_pagespeed_unavailable_marks_partial(self) -> None:
        result = score_scan(
            PageSpeedData(available=False),
            _full_browser(),
            _full_http(),
        )
        assert result["scan_partial"] is True
        assert result["overall"] is None
        assert result["score_performance"] is None
        # SEO / AI / Security still measurable.
        assert result["score_seo"] is not None
        assert result["score_ai_readiness"] is not None
        assert result["score_security"] is not None

    def test_weights_sum_to_one(self) -> None:
        assert WEIGHT_PERFORMANCE + WEIGHT_SEO + WEIGHT_AI + WEIGHT_SECURITY == 1.0


class TestPerformanceFindings:
    def test_slow_lcp_triggers_high_severity(self) -> None:
        result = score_scan(
            PageSpeedData(mobile=_perf(20, lcp=5200), available=True),
            _full_browser(),
            _full_http(),
        )
        high_perf = [f for f in result["findings"] if f.category == "performance" and f.severity == "high"]
        assert high_perf, "expected a high-severity performance finding for LCP=5200ms"

    def test_heavy_page_triggers_finding(self) -> None:
        result = score_scan(
            PageSpeedData(mobile=_perf(30, weight=4_000_000), available=True),
            _full_browser(),
            _full_http(),
        )
        assert any(
            "MB" in f.smb_message and f.category == "performance"
            for f in result["findings"]
        )


class TestSeoFindings:
    def test_missing_meta_description_triggers_finding(self) -> None:
        browser = _full_browser()
        browser.meta_description = None
        result = score_scan(
            PageSpeedData(mobile=_perf(60), available=True), browser, _full_http()
        )
        assert any(f.category == "seo" and "description" in f.smb_message.lower()
                   for f in result["findings"])

    def test_missing_sitemap_triggers_finding(self) -> None:
        http = _full_http()
        http.sitemap_present = False
        result = score_scan(
            PageSpeedData(mobile=_perf(60), available=True), _full_browser(), http
        )
        assert any("sitemap" in f.technical_detail.lower() for f in result["findings"])


class TestAiReadinessFindings:
    def test_no_json_ld_triggers_finding(self) -> None:
        browser = _full_browser()
        browser.json_ld_types = []
        result = score_scan(
            PageSpeedData(mobile=_perf(60), available=True), browser, _full_http()
        )
        assert any(f.category == "ai_readiness" and "ai" in f.smb_message.lower()
                   for f in result["findings"])

    def test_zero_h1_triggers_finding(self) -> None:
        browser = _full_browser()
        browser.h1_count = 0
        result = score_scan(
            PageSpeedData(mobile=_perf(60), available=True), browser, _full_http()
        )
        assert any(f.category == "ai_readiness" and "heading" in f.smb_message.lower()
                   for f in result["findings"])

    def test_recognized_json_ld_awards_full_30(self) -> None:
        browser = _full_browser()
        browser.json_ld_types = ["MovingCompany"]
        result_full = score_scan(
            PageSpeedData(mobile=_perf(60), available=True), browser, _full_http()
        )
        browser.json_ld_types = []
        result_none = score_scan(
            PageSpeedData(mobile=_perf(60), available=True), browser, _full_http()
        )
        assert result_full["score_ai_readiness"] > result_none["score_ai_readiness"]


class TestSecurityScoring:
    def test_all_headers_gives_100(self) -> None:
        result = score_scan(
            PageSpeedData(mobile=_perf(60), available=True),
            _full_browser(),
            _full_http(),
        )
        assert result["score_security"] == 100

    def test_no_headers_gives_0_and_finding(self) -> None:
        http = _full_http()
        http.has_hsts = False
        http.has_csp = False
        http.has_x_frame_options = False
        http.has_x_content_type_options = False
        http.has_referrer_policy = False
        result = score_scan(
            PageSpeedData(mobile=_perf(60), available=True), _full_browser(), http
        )
        assert result["score_security"] == 0
        assert any(f.category == "security" for f in result["findings"])


class TestBrowserUnavailable:
    def test_browser_failure_marks_seo_and_ai_unmeasurable(self) -> None:
        result = score_scan(
            PageSpeedData(mobile=_perf(60), available=True),
            BrowserCheckResult(available=False, error_reason="timeout"),
            _full_http(),
        )
        assert result["score_seo"] is None
        assert result["score_ai_readiness"] is None
        assert result["scan_partial"] is True
        assert result["overall"] is None
