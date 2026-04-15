"""Pure scoring function.

Given ``PageSpeedData``, ``BrowserCheckResult``, and ``HttpCheckResult``,
produce:

- Four dimension scores 0-100 (any may be ``None`` if unmeasurable).
- A composite ``overall`` score — ``None`` whenever any dimension is
  ``None`` (we don't silently rescale).
- A list of ``Finding`` instances with SMB-ready copy.

This module has no side effects and no IO. Every finding's SMB message
lives right next to the rule that triggers it — one file, one place to
read the full scoring logic.

Weights (locked per decisions from CEO + eng review):
    Performance 45% | SEO 20% | AI-Readiness 20% | Security 15%
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pipeline.agents.scanner.base import (
    BrowserCheckResult,
    Finding,
    HttpCheckResult,
    PageSpeedData,
    PageSpeedResult,
)

WEIGHT_PERFORMANCE = 0.45
WEIGHT_SEO = 0.20
WEIGHT_AI = 0.20
WEIGHT_SECURITY = 0.15

# Thresholds come from PageSpeed's own "good / needs improvement / poor" bands.
LCP_GOOD_MS = 2500
LCP_POOR_MS = 4000
CLS_GOOD = 0.1
CLS_POOR = 0.25
TBT_GOOD_MS = 200
TBT_POOR_MS = 600
PAGE_WEIGHT_HIGH_BYTES = 3_000_000  # 3 MB
PAGE_WEIGHT_MEDIUM_BYTES = 1_500_000

IMAGE_ALT_GOOD = 0.8

PASS_FAIL_THRESHOLD = 70  # decorative only — admin dashboard convenience


def score_scan(
    pagespeed: PageSpeedData,
    browser: BrowserCheckResult,
    http: HttpCheckResult,
) -> dict[str, Any]:
    """Return per-dimension scores, overall, findings, and raw metrics."""
    findings: list[Finding] = []
    raw: dict[str, Any] = {}

    perf_score = _score_performance(pagespeed, findings, raw)
    seo_score = _score_seo(pagespeed, browser, http, findings)
    ai_score = _score_ai(browser, http, findings)
    sec_score = _score_security(http, findings)
    _emit_conversion_findings(browser, findings)

    dims = {
        "score_performance": perf_score,
        "score_seo": seo_score,
        "score_ai_readiness": ai_score,
        "score_security": sec_score,
    }
    scan_partial = any(v is None for v in dims.values())
    overall = None if scan_partial else _weighted_overall(
        perf_score, seo_score, ai_score, sec_score
    )

    return {
        **dims,
        "overall": overall,
        "scan_partial": scan_partial,
        "findings": findings,
        "raw_metrics": raw,
    }


def _weighted_overall(perf: int, seo: int, ai: int, sec: int) -> int:
    return int(
        round(
            perf * WEIGHT_PERFORMANCE
            + seo * WEIGHT_SEO
            + ai * WEIGHT_AI
            + sec * WEIGHT_SECURITY
        )
    )


# ── Performance ──────────────────────────────────────────────────────────────


def _score_performance(
    ps: PageSpeedData, findings: list[Finding], raw: dict[str, Any]
) -> int | None:
    if not ps.available or (ps.mobile is None and ps.desktop is None):
        return None

    # Capture raw metrics from whichever strategy is present (mobile preferred).
    primary = ps.mobile or ps.desktop
    assert primary is not None
    raw["lcp_ms"] = primary.lcp_ms
    raw["fcp_ms"] = primary.fcp_ms
    raw["cls"] = primary.cls
    raw["tbt_ms"] = primary.tbt_ms
    raw["ttfb_ms"] = primary.ttfb_ms
    raw["speed_index_ms"] = primary.speed_index_ms
    raw["page_weight_bytes"] = primary.page_weight_bytes

    scores_seen = [s for s in (_perf_or_none(ps.mobile), _perf_or_none(ps.desktop)) if s is not None]
    if not scores_seen:
        return None
    perf = int(round(sum(scores_seen) / len(scores_seen)))

    # ── Findings ──
    lcp = primary.lcp_ms
    if lcp is not None and lcp > LCP_POOR_MS:
        findings.append(Finding(
            category="performance", severity="high",
            smb_message=(
                f"Your site takes {lcp / 1000:.1f} seconds to load on mobile. "
                "The typical visitor gives up after 3."
            ),
            technical_detail=f"LCP={lcp:.0f}ms (good <{LCP_GOOD_MS}ms, poor >{LCP_POOR_MS}ms)",
        ))
    elif lcp is not None and lcp > LCP_GOOD_MS:
        findings.append(Finding(
            category="performance", severity="medium",
            smb_message=(
                f"Your site takes {lcp / 1000:.1f} seconds to load on mobile — "
                "slow enough that mobile visitors start bouncing."
            ),
            technical_detail=f"LCP={lcp:.0f}ms (good <{LCP_GOOD_MS}ms)",
        ))

    cls = primary.cls
    if cls is not None and cls > CLS_POOR:
        findings.append(Finding(
            category="performance", severity="medium",
            smb_message=(
                "Elements on your page jump around while it loads — visitors find this "
                "disorienting and lose trust."
            ),
            technical_detail=f"CLS={cls:.2f} (good <{CLS_GOOD}, poor >{CLS_POOR})",
        ))

    tbt = primary.tbt_ms
    if tbt is not None and tbt > TBT_POOR_MS:
        findings.append(Finding(
            category="performance", severity="medium",
            smb_message=(
                "Your site is unresponsive for about "
                f"{tbt / 1000:.1f} seconds after it loads — tapping a button does nothing."
            ),
            technical_detail=f"TBT={tbt:.0f}ms (good <{TBT_GOOD_MS}ms, poor >{TBT_POOR_MS}ms)",
        ))

    weight = primary.page_weight_bytes
    if weight is not None and weight > PAGE_WEIGHT_HIGH_BYTES:
        findings.append(Finding(
            category="performance", severity="medium",
            smb_message=(
                f"Your site is {weight / 1_000_000:.1f}MB — visitors on mobile data "
                "are paying to load an inflated site."
            ),
            technical_detail=f"total-byte-weight={weight}",
        ))

    return perf


def _perf_or_none(r: PageSpeedResult | None) -> int | None:
    if r is None:
        return None
    return r.performance_score


# ── SEO ─────────────────────────────────────────────────────────────────────


def _score_seo(
    ps: PageSpeedData,
    browser: BrowserCheckResult,
    http: HttpCheckResult,
    findings: list[Finding],
) -> int | None:
    if not browser.available:
        return None

    points = 0
    if browser.meta_description and len(browser.meta_description) >= 50:
        points += 15
    else:
        findings.append(Finding(
            category="seo", severity="medium",
            smb_message=(
                "Your site has no description for Google — so Google pulls random text "
                "from the page to show in search results."
            ),
            technical_detail="<meta name='description'> missing or too short (<50 chars)",
        ))
    if browser.title and 30 <= len(browser.title) <= 60:
        points += 10
    elif not browser.title:
        findings.append(Finding(
            category="seo", severity="high",
            smb_message="Your site has no title — search results show a blank line where your business name should be.",
            technical_detail="<title> missing",
        ))
    if browser.canonical_url:
        points += 10
    og_complete = all([browser.og_title, browser.og_description, browser.og_image])
    if og_complete:
        points += 25
    else:
        findings.append(Finding(
            category="seo", severity="low",
            smb_message=(
                "When someone shares your site on Facebook or iMessage, it shows up without "
                "a preview image — links with previews get 2-3× more clicks."
            ),
            technical_detail="incomplete Open Graph tags (og:title, og:description, og:image)",
        ))
    if http.available and http.sitemap_present:
        points += 15
    else:
        findings.append(Finding(
            category="seo", severity="medium",
            smb_message=(
                "Google has no sitemap for your site, so new pages take weeks to show up in "
                "search results instead of days."
            ),
            technical_detail="sitemap.xml not found",
        ))
    if http.available and http.robots_present and not http.robots_blocks_all:
        points += 10
    if browser.json_ld_types:
        points += 7

    # Adjustment from PageSpeed's SEO category (max +8).
    ps_seo = _best_category(ps, "seo_score")
    if ps_seo is not None:
        points += int(round(ps_seo * 0.08))

    return min(100, points)


def _best_category(ps: PageSpeedData, attr: str) -> int | None:
    scores = [
        getattr(r, attr)
        for r in (ps.mobile, ps.desktop)
        if r is not None and getattr(r, attr) is not None
    ]
    return max(scores) if scores else None


# ── AI-Readiness ────────────────────────────────────────────────────────────


_RECOGNIZED_JSON_LD_TYPES = frozenset(
    {
        "Organization", "LocalBusiness", "Product", "Service", "Article",
        "WebSite", "WebPage", "BreadcrumbList", "Event", "Restaurant",
        "ProfessionalService", "MovingCompany", "FAQPage", "HowTo",
    }
)


def _score_ai(
    browser: BrowserCheckResult, http: HttpCheckResult, findings: list[Finding]
) -> int | None:
    if not browser.available:
        return None

    points = 0
    if browser.json_ld_types and any(
        t in _RECOGNIZED_JSON_LD_TYPES for t in browser.json_ld_types
    ):
        points += 30
    else:
        findings.append(Finding(
            category="ai_readiness", severity="low",
            smb_message=(
                "AI assistants (ChatGPT, Google AI) can't reliably understand what your "
                "business does — they need structured data to quote you."
            ),
            technical_detail="no recognized JSON-LD @type (Organization/LocalBusiness/etc.)",
        ))
    if http.available and http.llms_txt_present:
        points += 20
    if browser.h1_count == 1:
        points += 15
    elif browser.h1_count == 0:
        findings.append(Finding(
            category="ai_readiness", severity="medium",
            smb_message="Your site has no main heading — AI and search engines can't tell what this page is about.",
            technical_detail="no <h1> on page",
        ))
    elif browser.h1_count > 1:
        findings.append(Finding(
            category="ai_readiness", severity="low",
            smb_message="Your site has multiple main headings, which confuses search engines about the page's topic.",
            technical_detail=f"<h1> count = {browser.h1_count}",
        ))
    if browser.heading_hierarchy_ok:
        points += 10
    if browser.image_count > 0 and (
        browser.images_with_alt / browser.image_count
    ) >= IMAGE_ALT_GOOD:
        points += 10
    elif browser.image_count > 0:
        pct = browser.images_with_alt / browser.image_count
        findings.append(Finding(
            category="ai_readiness", severity="low",
            smb_message=(
                f"Only {pct * 100:.0f}% of your images have descriptions — search engines "
                "can't read images without them, and visually-impaired visitors can't either."
            ),
            technical_detail=f"images with alt: {browser.images_with_alt}/{browser.image_count}",
        ))
    if browser.meta_description:
        points += 10
    if browser.canonical_url:
        points += 5

    return min(100, points)


# ── Security ────────────────────────────────────────────────────────────────


def _score_security(http: HttpCheckResult, findings: list[Finding]) -> int | None:
    if not http.available:
        return None

    points = 0
    missing: list[str] = []
    if http.has_hsts:
        points += 25
    else:
        missing.append("HSTS (prevents downgrade to HTTP)")
    if http.has_csp:
        points += 25
    else:
        missing.append("CSP (prevents script-injection attacks)")
    if http.has_x_frame_options:
        points += 20
    else:
        missing.append("X-Frame-Options (prevents clickjacking)")
    if http.has_x_content_type_options:
        points += 20
    else:
        missing.append("X-Content-Type-Options")
    if http.has_referrer_policy:
        points += 10
    else:
        missing.append("Referrer-Policy")

    if missing and points < 50:
        findings.append(Finding(
            category="security", severity="low",
            smb_message=(
                "Your site is missing standard security protections — "
                "visible to any developer inspecting your site and a red flag for enterprise buyers."
            ),
            technical_detail="missing headers: " + ", ".join(missing),
        ))

    return points


# ── Conversion findings ─────────────────────────────────────────────────────
#
# Conversion is deliberately NOT a scored dimension — a scalar "Conversion: 42"
# is weaker than specific observations. The Sales Agent reads these findings
# and drops their SMB messages into cold-email copy. Each rule is cheap to
# compute from the single Playwright session.

COPYRIGHT_YEAR_STALE_THRESHOLD = 2  # years behind current


def _emit_conversion_findings(
    browser: BrowserCheckResult, findings: list[Finding]
) -> None:
    if not browser.available:
        return

    # 1. Phone visible above the fold.
    if not browser.phone_above_fold:
        findings.append(Finding(
            category="conversion", severity="high",
            smb_message=(
                "Your phone number isn't visible in the first screen visitors see. "
                "For local services, most bookings happen by phone call."
            ),
            technical_detail="no tel: link or phone number detected in the top viewport",
        ))

    # 2. CTA above the fold.
    if not browser.cta_above_fold:
        findings.append(Finding(
            category="conversion", severity="high",
            smb_message=(
                "Nothing on your homepage tells visitors what to do next in the first "
                "screen. No 'Get a Quote', no 'Call Now', no 'Book' button where they "
                "can see it."
            ),
            technical_detail="no CTA-ish button or link in the top viewport",
        ))

    # 3. Contact form anywhere on the site.
    if not browser.has_contact_form:
        findings.append(Finding(
            category="conversion", severity="medium",
            smb_message=(
                "Your site has no contact form — every inquiry routes through email "
                "or phone instead of a visitor typing and clicking once."
            ),
            technical_detail="no <form> with text/email/tel/textarea inputs found",
        ))

    # 4. Copyright year stale (or missing).
    current_year = datetime.now(tz=timezone.utc).year
    if browser.copyright_year is not None:
        years_behind = current_year - browser.copyright_year
        if years_behind >= COPYRIGHT_YEAR_STALE_THRESHOLD:
            findings.append(Finding(
                category="conversion", severity="medium",
                smb_message=(
                    f"Your site's copyright says © {browser.copyright_year} — "
                    "new visitors start to wonder if you're still in business."
                ),
                technical_detail=f"footer copyright year = {browser.copyright_year} ({years_behind} years behind)",
            ))

    # 5. Reviews / testimonials visible.
    if not browser.has_reviews_or_testimonials:
        findings.append(Finding(
            category="conversion", severity="medium",
            smb_message=(
                "No reviews or testimonials on your homepage. Visitors comparing "
                "you against the next result on Google have no reason to pick you."
            ),
            technical_detail=(
                "no JSON-LD Review/AggregateRating, no testimonial keywords, "
                "no star-rating text on page"
            ),
        ))


__all__ = ["score_scan", "PASS_FAIL_THRESHOLD"]
