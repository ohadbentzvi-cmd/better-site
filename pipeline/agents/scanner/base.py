"""Core types for the Scanner.

Every check returns a typed pydantic model (no raw dicts), so the scoring
function gets validated input and can't silently crash on missing keys.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

# ── Target input ─────────────────────────────────────────────────────────────


class TargetUrl(BaseModel):
    """One URL the scanner should process."""

    url: str
    lead_id: uuid.UUID | None = None  # None in pure URL-list mode


@runtime_checkable
class ScanTarget(Protocol):
    """Anything that yields URLs to scan. Mirrors the Lead Generator pattern."""

    name: str

    def iter_targets(self) -> AsyncIterator[TargetUrl]: ...


# ── Check results (validated pydantic models, not raw dicts) ─────────────────


class PageSpeedResult(BaseModel):
    """What the PageSpeed Insights API returns for a single strategy.

    Every field is Optional so the scorer degrades gracefully when Google
    ships a partial payload (common for really slow sites).
    """

    strategy: Literal["mobile", "desktop"]
    performance_score: int | None = None  # 0-100
    seo_score: int | None = None
    best_practices_score: int | None = None

    lcp_ms: float | None = None        # Largest Contentful Paint
    fcp_ms: float | None = None        # First Contentful Paint
    cls: float | None = None           # Cumulative Layout Shift
    tbt_ms: float | None = None        # Total Blocking Time
    ttfb_ms: float | None = None       # Time To First Byte
    speed_index_ms: float | None = None

    page_weight_bytes: int | None = None
    unused_css_score: float | None = None
    unused_js_score: float | None = None
    render_blocking_score: float | None = None


class PageSpeedData(BaseModel):
    """Both strategies together. Missing strategies = None."""

    mobile: PageSpeedResult | None = None
    desktop: PageSpeedResult | None = None
    available: bool = True  # False when both strategies failed


class BrowserCheckResult(BaseModel):
    """Playwright-derived DOM + screenshots."""

    available: bool = True
    title: str | None = None
    meta_description: str | None = None
    canonical_url: str | None = None
    og_title: str | None = None
    og_description: str | None = None
    og_image: str | None = None
    has_viewport_meta: bool = False
    viewport_content: str | None = None

    h1_count: int = 0
    h2_count: int = 0
    h3_count: int = 0
    heading_hierarchy_ok: bool = True

    image_count: int = 0
    images_with_alt: int = 0

    json_ld_types: list[str] = Field(default_factory=list)  # ["LocalBusiness", ...]

    # ── Conversion signals (above-the-fold + site-wide) ─────────────────────
    phone_above_fold: bool = False
    phone_text: str | None = None       # first tel: or phone regex match near top
    cta_above_fold: bool = False
    cta_text: str | None = None         # first CTA-ish button/link text
    has_contact_form: bool = False
    copyright_year: int | None = None   # max 4-digit year found in footer/body
    has_reviews_or_testimonials: bool = False

    desktop_screenshot_png: bytes | None = None  # 1280x900 full-page
    mobile_screenshot_png: bytes | None = None   # 375x812 full-page

    # If the site blocked us / Playwright crashed, set False + error_reason.
    error_reason: str | None = None

    model_config = {"arbitrary_types_allowed": True}


class HttpCheckResult(BaseModel):
    """Robots/sitemap/llms/security headers — pure HTTP, no browser."""

    available: bool = True

    robots_present: bool = False
    robots_blocks_all: bool = False

    llms_txt_present: bool = False

    sitemap_present: bool = False
    sitemap_url_count: int = 0

    # Security headers on the main URL.
    has_hsts: bool = False
    has_csp: bool = False
    has_x_frame_options: bool = False
    has_x_content_type_options: bool = False
    has_referrer_policy: bool = False

    error_reason: str | None = None


# ── Finding + ScanResult ─────────────────────────────────────────────────────


FindingCategory = Literal[
    "performance", "mobile", "seo", "ai_readiness", "security", "conversion"
]
FindingSeverity = Literal["high", "medium", "low"]


class Finding(BaseModel):
    """A single issue surfaced by the scanner.

    ``smb_message`` is the email-ready copy — the Sales Agent drops it
    straight into cold-email templates. ``technical_detail`` is for
    admin review.
    """

    category: FindingCategory
    severity: FindingSeverity
    smb_message: str
    technical_detail: str
    evidence_url: str | None = None


class ScanResult(BaseModel):
    """Everything produced for a single URL."""

    url: str
    scanned_url: str  # after redirects / canonicalization

    # Dimension scores 0-100. None when the dimension was unmeasurable.
    score_performance: int | None = None
    score_seo: int | None = None
    score_ai_readiness: int | None = None
    score_security: int | None = None

    overall: int | None = None
    scan_partial: bool = False

    pagespeed_available: bool = True

    # PageSpeed category score convenience fields for the scans table.
    pagespeed_mobile: int | None = None
    pagespeed_desktop: int | None = None

    # Legacy booleans for admin UI.
    has_ssl: bool = False
    has_mobile: bool = False
    has_analytics: bool = False

    raw_metrics: dict[str, Any] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}


__all__ = [
    "BrowserCheckResult",
    "Finding",
    "FindingCategory",
    "FindingSeverity",
    "HttpCheckResult",
    "PageSpeedData",
    "PageSpeedResult",
    "ScanResult",
    "ScanTarget",
    "TargetUrl",
]
