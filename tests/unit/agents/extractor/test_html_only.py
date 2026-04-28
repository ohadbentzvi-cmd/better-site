"""Unit tests for the html_only extraction strategy.

Pure HTML / regex tests — no Playwright, no R2, no network. Each helper is
exercised against a small inline fixture so the failure mode is obvious.
The end-to-end happy path lives in the integration suite.
"""

from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from pipeline.agents.extractor.strategies.html_only import (
    _extract_about,
    _extract_business_name,
    _extract_cta_text,
    _extract_email,
    _extract_license_numbers,
    _extract_phone,
    _extract_social_links,
    _extract_tagline,
    _extract_years_in_business,
    _is_tracking_image_url,
    _pick_title_segment,
)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


# ── Business name ───────────────────────────────────────────────────────────


def test_business_name_prefers_og_site_name() -> None:
    s = _soup(
        '<html><head>'
        '<meta property="og:site_name" content="Acme Movers">'
        '<title>generic fallback</title>'
        '</head><body><h1>Header</h1></body></html>'
    )
    assert _extract_business_name(s, "https://acmemovers.com") == "Acme Movers"


def test_business_name_falls_back_to_og_title_with_smart_split() -> None:
    s = _soup(
        '<html><head>'
        '<meta property="og:title" content="Acme Movers - Houston, TX">'
        '<title>generic</title>'
        '</head></html>'
    )
    assert _extract_business_name(s, "https://acmemovers.com") == "Acme Movers"


def test_business_name_smart_split_picks_domain_matching_segment() -> None:
    # Title leads with a service heading; the brand is on the right.
    s = _soup(
        '<html><head><title>Long Distance Movers - America\'s Moving Services</title></head></html>'
    )
    assert (
        _extract_business_name(s, "https://americasmovingservices.com")
        == "America's Moving Services"
    )


def test_business_name_logo_alt_fallback() -> None:
    s = _soup(
        '<html><head><title></title></head><body>'
        '<header><img src="/brand.png" alt="Acme Brand"></header>'
        '</body></html>'
    )
    assert _extract_business_name(s, "https://example.com") == "Acme Brand"


def test_business_name_skips_logo_alt_containing_logo_word() -> None:
    s = _soup(
        '<html><head></head><body>'
        '<header><img src="/logo.png" alt="Acme logo"></header>'
        '<h1>Acme Movers</h1>'
        '</body></html>'
    )
    assert _extract_business_name(s, "https://example.com") == "Acme Movers"


def test_business_name_returns_none_when_nothing_matches() -> None:
    s = _soup("<html><head></head><body></body></html>")
    assert _extract_business_name(s, "https://example.com") is None


# ── Title segment picking ───────────────────────────────────────────────────


def test_pick_title_segment_single_segment_passthrough() -> None:
    assert _pick_title_segment("Just One", "https://example.com") == "Just One"


def test_pick_title_segment_picks_domain_matching_side() -> None:
    title = "Long Distance | America's Moving Services"
    assert (
        _pick_title_segment(title, "https://americasmovingservices.com")
        == "America's Moving Services"
    )


def test_pick_title_segment_falls_back_to_first_when_no_match() -> None:
    title = "Generic Tagline | Some Business"
    assert _pick_title_segment(title, "https://example.com") == "Generic Tagline"


def test_pick_title_segment_strips_dash_separators() -> None:
    # em-dash, en-dash, hyphen all behave the same
    assert _pick_title_segment("A — B", "https://b.com") == "B"


# ── Tagline ─────────────────────────────────────────────────────────────────


def test_tagline_from_meta_description() -> None:
    s = _soup(
        '<html><head><meta name="description" content="The best movers in town."></head></html>'
    )
    assert _extract_tagline(s) == "The best movers in town."


def test_tagline_falls_back_to_og_description() -> None:
    s = _soup(
        '<html><head><meta property="og:description" content="OG fallback copy."></head></html>'
    )
    assert _extract_tagline(s) == "OG fallback copy."


# ── CTA ─────────────────────────────────────────────────────────────────────


def test_cta_text_picks_first_hint_match() -> None:
    s = _soup(
        '<html><body>'
        '<a href="/about">About Us</a>'
        '<a href="/quote">Get a Free Quote</a>'
        '<a href="/services">Services</a>'
        '</body></html>'
    )
    assert _extract_cta_text(s) == "Get a Free Quote"


def test_cta_text_returns_none_when_no_hints() -> None:
    s = _soup(
        '<html><body><a href="/about">About</a><a href="/services">Services</a></body></html>'
    )
    assert _extract_cta_text(s) is None


# ── Phone ───────────────────────────────────────────────────────────────────


def test_phone_from_tel_href() -> None:
    s = _soup('<html><body><a href="tel:+18888880000">Call</a></body></html>')
    text = s.get_text(" ", strip=True)
    assert _extract_phone(s, text) == "+18888880000"


def test_phone_regex_fallback_when_no_tel_href() -> None:
    s = _soup("<html><body><p>Call us at (888) 555-1212 today!</p></body></html>")
    text = s.get_text(" ", strip=True)
    assert _extract_phone(s, text) == "(888) 555-1212"


# ── Email ───────────────────────────────────────────────────────────────────


def test_email_from_mailto_strips_query() -> None:
    s = _soup(
        '<html><body><a href="mailto:hello@acme.com?subject=quote">Email</a></body></html>'
    )
    text = s.get_text(" ", strip=True)
    assert _extract_email(s, text) == "hello@acme.com"


def test_email_regex_fallback() -> None:
    s = _soup("<html><body><p>Contact: hello@acme.com</p></body></html>")
    text = s.get_text(" ", strip=True)
    assert _extract_email(s, text) == "hello@acme.com"


# ── Years in business ───────────────────────────────────────────────────────


def test_years_in_business_since_year() -> None:
    text = "Family-owned and operated since 2000."
    yrs = _extract_years_in_business(text)
    expected = datetime.now(timezone.utc).year - 2000
    assert yrs == expected


def test_years_in_business_n_years_phrase() -> None:
    text = "Over 35 years of experience moving Houston."
    assert _extract_years_in_business(text) == 35


def test_years_in_business_no_match_returns_none() -> None:
    assert _extract_years_in_business("We just love moving!") is None


# ── License numbers ─────────────────────────────────────────────────────────


def test_license_numbers_extracts_all_variants() -> None:
    text = "USDOT #123456 and MC 7891011 — DOT 22222 in our footer"
    out = _extract_license_numbers(text)
    assert "USDOT 123456" in out
    assert "MC 7891011" in out
    assert "DOT 22222" in out


def test_license_numbers_dedupes_repeats() -> None:
    text = "USDOT 123456 USDOT 123456"
    assert _extract_license_numbers(text) == ["USDOT 123456"]


# ── About ───────────────────────────────────────────────────────────────────


def test_about_skips_footer_p() -> None:
    real_about = (
        "Acme Movers is a 4th generation family business serving Houston since 2000. "
        "We do residential and commercial moves with a focus on care and quality."
    )
    html = (
        "<html><body>"
        f"<main><p>{real_about}</p></main>"
        "<footer><p>Copyright 2026 — All rights reserved. "
        "Some other content here for length matching.</p></footer>"
        "</body></html>"
    )
    out = _extract_about(_soup(html))
    assert out is not None
    assert "Copyright" not in out
    assert "Acme Movers" in out


def test_about_skips_copyright_p() -> None:
    real_about = (
        "We are locally owned out of Columbia, SC and have been in business since 2012. "
        "We have over 10 years of experience and specialize in packing and moving."
    )
    html = (
        "<html><body>"
        "<p>© 2026 ProHelp Movers — All Rights Reserved. "
        "Padding text to reach the eighty-character minimum length requirement.</p>"
        f"<p>{real_about}</p>"
        "</body></html>"
    )
    out = _extract_about(_soup(html))
    assert out is not None
    assert "©" not in out
    assert "Locally owned" in out or "locally owned" in out


# ── Social links ────────────────────────────────────────────────────────────


def test_social_links_filters_wix_placeholder() -> None:
    s = _soup(
        '<html><body>'
        '<a href="https://www.facebook.com/wix">FB placeholder</a>'
        '<a href="https://twitter.com/realbusiness">TW</a>'
        '</body></html>'
    )
    out = _extract_social_links(s, "https://example.com")
    assert "facebook" not in out
    assert out.get("twitter") == "https://twitter.com/realbusiness"


def test_social_links_excludes_self_host() -> None:
    s = _soup('<html><body><a href="https://example.com/blog">Blog</a></body></html>')
    out = _extract_social_links(s, "https://example.com")
    assert out == {}


def test_social_links_first_per_platform_wins() -> None:
    s = _soup(
        '<html><body>'
        '<a href="https://facebook.com/first">A</a>'
        '<a href="https://facebook.com/second">B</a>'
        '</body></html>'
    )
    out = _extract_social_links(s, "https://example.com")
    assert out["facebook"] == "https://facebook.com/first"


# ── Tracking image filter ───────────────────────────────────────────────────


def test_tracking_image_filter_blocks_facebook_pixel() -> None:
    assert _is_tracking_image_url(
        "https://www.facebook.com/tr?id=12345&ev=PageView"
    )


def test_tracking_image_filter_blocks_doubleclick() -> None:
    assert _is_tracking_image_url("https://stats.g.doubleclick.net/dc.js")


def test_tracking_image_filter_blocks_googletagmanager() -> None:
    assert _is_tracking_image_url("https://www.googletagmanager.com/gtag/js")


def test_tracking_image_filter_allows_normal_cdn() -> None:
    assert not _is_tracking_image_url("https://cdn.example.com/hero.jpg")


def test_tracking_image_filter_allows_facebook_profile_link() -> None:
    # facebook.com/somecompany is a regular profile link, not /tr
    assert not _is_tracking_image_url("https://facebook.com/acmemovers")
