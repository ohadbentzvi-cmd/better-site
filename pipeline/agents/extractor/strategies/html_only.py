"""HTML-only extraction strategy.

Deterministic baseline — no Claude calls. BeautifulSoup for text,
ColorThief on the screenshot for brand colors, simple DOM heuristics for
logo + hero candidates. Fields whose heuristics don't match stay
``None`` / ``[]``; the template handles graceful degradation. The
vision_full + hybrid strategies (TODOS T4) close gaps measured against
this baseline.
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx
import structlog
from bs4 import BeautifulSoup, Tag
from colorthief import ColorThief

from pipeline.agents.extractor.base import (
    ExtractionResult,
    ExtractionStrategy,
    ServiceBlurb,
    Testimonial,
)
from pipeline.agents.extractor.registry import register
from pipeline.utils import r2
from pipeline.utils.image_fetch import ImageFetchError, fetch_image
from pipeline.utils.ssrf import UnsafeUrlError
from pipeline.utils.url import InvalidURLError, canonicalize_domain

log = structlog.get_logger(__name__)


# ── Regex constants ──────────────────────────────────────────────────────────

_PHONE_RE = re.compile(r"(?:\+?1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_SINCE_YEAR_RE = re.compile(
    r"\b(?:since|established(?:\s+in)?|founded(?:\s+in)?|est\.?)\s+(\d{4})\b",
    re.IGNORECASE,
)
_YEARS_EXPERIENCE_RE = re.compile(
    r"\b(?:over|more\s+than)?\s*(\d{1,3})\s*\+?\s*years?\b", re.IGNORECASE
)
_LICENSE_RE = re.compile(
    r"\b(US\s*DOT|USDOT|DOT|MC)\s*#?\s*(\d{4,8})\b", re.IGNORECASE
)


# ── Social link mapping ──────────────────────────────────────────────────────

_SOCIAL_DOMAINS: dict[str, str] = {
    "facebook.com": "facebook",
    "fb.com": "facebook",
    "instagram.com": "instagram",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "linkedin.com": "linkedin",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "tiktok.com": "tiktok",
    "pinterest.com": "pinterest",
    "yelp.com": "yelp",
}

# Template placeholders that ship with site builders (Wix etc.) and that
# owners frequently forget to replace. Path-exact match after lowercase.
_SOCIAL_PLACEHOLDER_PATHS: frozenset[str] = frozenset(
    {
        "/wix",
        "/sample",
        "/example",
        "/demo",
        "/yourpage",
        "/your-page",
        "/yourcompany",
        "/your-company",
        "/yourbusiness",
        "/your-business",
        "/your_user_name",
    }
)


# ── Tracking / analytics hosts ──────────────────────────────────────────────

# Hosts whose images are pixels or beacons, never real assets. Used to
# filter logo/hero candidates so a Facebook tracking pixel can't be picked
# as the largest <img> on the page.
_TRACKING_HOSTS: frozenset[str] = frozenset(
    {
        "google-analytics.com",
        "googletagmanager.com",
        "doubleclick.net",
        "bat.bing.com",
        "ct.pinterest.com",
        "static.hotjar.com",
        "script.hotjar.com",
        "cdn.segment.com",
    }
)


# ── CTA detection ────────────────────────────────────────────────────────────

_CTA_HINTS: tuple[str, ...] = (
    "free quote",
    "get a quote",
    "request a quote",
    "book now",
    "book online",
    "schedule",
    "contact us",
    "call now",
    "get started",
    "free estimate",
    "request estimate",
)


# ── Section-heading hints ────────────────────────────────────────────────────

_SERVICE_HEADING_HINTS: tuple[str, ...] = (
    "service",
    "what we do",
    "our work",
    "what we offer",
)
_AREAS_HEADING_HINTS: tuple[str, ...] = (
    "service area",
    "areas we serve",
    "where we serve",
    "cities we serve",
)
_ABOUT_HEADING_HINTS: tuple[str, ...] = (
    "about",
    "who we are",
    "our story",
)


# ── Output caps ──────────────────────────────────────────────────────────────

_MAX_ABOUT_CHARS = 600
_MAX_SERVICES = 8
_MAX_AREAS = 12
_MAX_TESTIMONIALS = 5
_MAX_LICENSES = 4
_BRAND_COLOR_COUNT = 5


@register
class HtmlOnlyStrategy(ExtractionStrategy):
    name = "html_only"

    def extract(
        self,
        url: str,
        html: str,
        screenshot_png: bytes,
    ) -> ExtractionResult:
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ", strip=True)

        return ExtractionResult(
            business_name=_extract_business_name(soup, url),
            tagline=_extract_tagline(soup),
            cta_text=_extract_cta_text(soup),
            years_in_business=_extract_years_in_business(text),
            license_numbers=_extract_license_numbers(text),
            phone=_extract_phone(soup, text),
            email=_extract_email(soup, text),
            address=_extract_address(soup),
            hours=_extract_hours(soup),
            about=_extract_about(soup),
            services=_extract_services(soup),
            service_areas=_extract_service_areas(soup),
            testimonials=_extract_testimonials(soup),
            social_links=_extract_social_links(soup, url),
            logo_r2_key=_upload_logo(soup, url),
            hero_r2_key=_upload_hero(soup, url),
            brand_colors=_extract_brand_colors(screenshot_png),
            strategy_name=self.name,
            cost_usd=0.0,
        )


# ── Identity ────────────────────────────────────────────────────────────────


def _extract_business_name(soup: BeautifulSoup, page_url: str) -> str | None:
    site_name = _meta_content(soup, attrs={"property": "og:site_name"})
    if site_name:
        return site_name

    og_title = _meta_content(soup, attrs={"property": "og:title"})
    if og_title:
        return _pick_title_segment(og_title, page_url)

    if soup.title and soup.title.string:
        return _pick_title_segment(soup.title.string.strip(), page_url)

    header = soup.find(["header", "nav"])
    if isinstance(header, Tag):
        for img in header.find_all("img"):
            if isinstance(img, Tag):
                alt = img.get("alt")
                if isinstance(alt, str) and alt.strip() and "logo" not in alt.lower():
                    return alt.strip()

    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        h1_text = h1.get_text(" ", strip=True)
        if h1_text:
            return h1_text

    return None


def _meta_content(soup: BeautifulSoup, attrs: dict[str, str]) -> str | None:
    el = soup.find("meta", attrs=attrs)
    if isinstance(el, Tag):
        content = el.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    return None


def _pick_title_segment(title: str, page_url: str) -> str:
    segments = [s.strip() for s in re.split(r"\s+[|·–—\-]\s+", title) if s.strip()]
    if not segments:
        return title.strip()
    if len(segments) == 1:
        return segments[0]
    try:
        domain = canonicalize_domain(page_url)
    except InvalidURLError:
        return segments[0]
    stem = domain.rsplit(".", 1)[0].lower()
    if stem:
        for seg in segments:
            normalized = re.sub(r"[^a-z0-9]", "", seg.lower())
            if stem in normalized:
                return seg
    return segments[0]


def _extract_tagline(soup: BeautifulSoup) -> str | None:
    desc = soup.find("meta", attrs={"name": "description"})
    if isinstance(desc, Tag):
        content = desc.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()

    og = soup.find("meta", attrs={"property": "og:description"})
    if isinstance(og, Tag):
        content = og.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()

    return None


def _extract_cta_text(soup: BeautifulSoup) -> str | None:
    for el in soup.find_all(["a", "button"]):
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        lower = text.lower()
        if any(hint in lower for hint in _CTA_HINTS):
            return text
    return None


# ── Trust ───────────────────────────────────────────────────────────────────


def _extract_years_in_business(text: str) -> int | None:
    since_match = _SINCE_YEAR_RE.search(text)
    if since_match:
        year = int(since_match.group(1))
        current = datetime.now(timezone.utc).year
        diff = current - year
        if 0 < diff < 200:
            return diff

    yrs_match = _YEARS_EXPERIENCE_RE.search(text)
    if yrs_match:
        n = int(yrs_match.group(1))
        if 0 < n < 200:
            return n

    return None


def _extract_license_numbers(text: str) -> list[str]:
    seen: list[str] = []
    for prefix, num in _LICENSE_RE.findall(text):
        clean_prefix = re.sub(r"\s+", "", prefix.upper())
        if clean_prefix == "USDOT":
            label = "USDOT"
        elif clean_prefix == "DOT":
            label = "DOT"
        else:
            label = clean_prefix
        formatted = f"{label} {num}"
        if formatted not in seen:
            seen.append(formatted)
        if len(seen) >= _MAX_LICENSES:
            break
    return seen


# ── Contact ─────────────────────────────────────────────────────────────────


def _extract_phone(soup: BeautifulSoup, text: str) -> str | None:
    for a in soup.find_all("a", href=True):
        href = a.get("href")
        if isinstance(href, str) and href.lower().startswith("tel:"):
            value = href[4:].strip()
            if value:
                return value

    match = _PHONE_RE.search(text)
    return match.group(0) if match else None


def _extract_email(soup: BeautifulSoup, text: str) -> str | None:
    for a in soup.find_all("a", href=True):
        href = a.get("href")
        if isinstance(href, str) and href.lower().startswith("mailto:"):
            value = href[7:].split("?")[0].strip()
            if value:
                return value

    match = _EMAIL_RE.search(text)
    return match.group(0) if match else None


def _extract_address(soup: BeautifulSoup) -> str | None:
    addr_tag = soup.find("address")
    if isinstance(addr_tag, Tag):
        addr_text = addr_tag.get_text(" ", strip=True)
        if addr_text:
            return addr_text

    for el in soup.find_all(attrs={"itemtype": re.compile("PostalAddress", re.I)}):
        if isinstance(el, Tag):
            t = el.get_text(" ", strip=True)
            if t:
                return t

    return None


def _extract_hours(soup: BeautifulSoup) -> dict[str, str]:
    hours: dict[str, str] = {}
    for el in soup.find_all(attrs={"itemprop": "openingHours"}):
        if isinstance(el, Tag):
            content = el.get("content")
            value = content if isinstance(content, str) else el.get_text(" ", strip=True)
            if value:
                hours[value] = value
    return hours


# ── Copy ────────────────────────────────────────────────────────────────────


def _extract_about(soup: BeautifulSoup) -> str | None:
    for heading in soup.find_all(["h1", "h2", "h3"]):
        head_text = heading.get_text(" ", strip=True).lower()
        if any(hint in head_text for hint in _ABOUT_HEADING_HINTS):
            for sib in heading.find_all_next(["p"], limit=3):
                if not isinstance(sib, Tag) or _p_is_boilerplate(sib):
                    continue
                text = sib.get_text(" ", strip=True)
                if len(text) >= 80:
                    return text[:_MAX_ABOUT_CHARS]
            break

    candidates = [
        p.get_text(" ", strip=True)
        for p in soup.find_all("p")
        if isinstance(p, Tag) and not _p_is_boilerplate(p)
    ]
    for text in sorted(candidates, key=len, reverse=True):
        if len(text) >= 80:
            return text[:_MAX_ABOUT_CHARS]
    return None


def _p_is_boilerplate(p: Tag) -> bool:
    text_lower = p.get_text(" ", strip=True).lower()
    if "©" in text_lower or "copyright" in text_lower:
        return True
    for parent in p.parents:
        if isinstance(parent, Tag) and parent.name == "footer":
            return True
    return False


def _extract_services(soup: BeautifulSoup) -> list[ServiceBlurb]:
    out: list[ServiceBlurb] = []
    for heading in soup.find_all(["h1", "h2", "h3"]):
        head_text = heading.get_text(" ", strip=True).lower()
        if not any(hint in head_text for hint in _SERVICE_HEADING_HINTS):
            continue

        list_el = heading.find_next(["ul", "ol"])
        if isinstance(list_el, Tag):
            for li in list_el.find_all("li", recursive=False):
                if not isinstance(li, Tag):
                    continue
                name = li.get_text(" ", strip=True)
                if name:
                    out.append(ServiceBlurb(name=name[:120]))
                if len(out) >= _MAX_SERVICES:
                    return out

        for sub in heading.find_all_next(["h3", "h4"], limit=_MAX_SERVICES * 2):
            if len(out) >= _MAX_SERVICES:
                break
            name = sub.get_text(" ", strip=True)
            if not name:
                continue
            blurb_p = sub.find_next("p")
            blurb = (
                blurb_p.get_text(" ", strip=True)[:240]
                if isinstance(blurb_p, Tag)
                else None
            )
            out.append(ServiceBlurb(name=name[:120], blurb=blurb))

        if out:
            break

    return out


def _extract_service_areas(soup: BeautifulSoup) -> list[str]:
    out: list[str] = []
    for heading in soup.find_all(["h1", "h2", "h3"]):
        head_text = heading.get_text(" ", strip=True).lower()
        if not any(hint in head_text for hint in _AREAS_HEADING_HINTS):
            continue

        list_el = heading.find_next(["ul", "ol"])
        if isinstance(list_el, Tag):
            for li in list_el.find_all("li", recursive=False):
                if not isinstance(li, Tag):
                    continue
                area = li.get_text(" ", strip=True)
                if area:
                    out.append(area[:80])
                if len(out) >= _MAX_AREAS:
                    return out
        if out:
            return out

    return out


def _extract_testimonials(soup: BeautifulSoup) -> list[Testimonial]:
    out: list[Testimonial] = []
    seen: set[str] = set()

    for el in soup.find_all(attrs={"itemtype": re.compile("Review", re.I)}):
        if not isinstance(el, Tag) or len(out) >= _MAX_TESTIMONIALS:
            continue
        body = el.find(attrs={"itemprop": "reviewBody"})
        author = el.find(attrs={"itemprop": "author"})
        quote = body.get_text(" ", strip=True) if isinstance(body, Tag) else None
        author_text = author.get_text(" ", strip=True) if isinstance(author, Tag) else None
        if quote and quote not in seen:
            out.append(Testimonial(quote=quote[:600], author=author_text, source=None))
            seen.add(quote)

    if out:
        return out

    pattern = re.compile(r"testimonial|review", re.IGNORECASE)
    for el in soup.find_all(attrs={"class": pattern}):
        if not isinstance(el, Tag) or len(out) >= _MAX_TESTIMONIALS:
            continue
        text = el.get_text(" ", strip=True)
        if len(text) < 40 or text in seen:
            continue
        out.append(Testimonial(quote=text[:600], author=None, source=None))
        seen.add(text)

    return out


# ── Social ──────────────────────────────────────────────────────────────────


def _extract_social_links(soup: BeautifulSoup, page_url: str) -> dict[str, str]:
    out: dict[str, str] = {}
    page_host = (urlparse(page_url).hostname or "").lower()

    for a in soup.find_all("a", href=True):
        href = a.get("href")
        if not isinstance(href, str):
            continue
        absolute = urljoin(page_url, href)
        parsed = urlparse(absolute)
        host = (parsed.hostname or "").lower()
        if not host or host == page_host:
            continue
        path = parsed.path.lower().rstrip("/")
        if path in _SOCIAL_PLACEHOLDER_PATHS:
            continue
        for domain, key in _SOCIAL_DOMAINS.items():
            if host == domain or host.endswith(f".{domain}"):
                if key not in out:
                    out[key] = absolute
                break
    return out


# ── Visual: brand colors ────────────────────────────────────────────────────


def _extract_brand_colors(screenshot_png: bytes) -> list[str]:
    if not screenshot_png:
        return []
    try:
        thief = ColorThief(io.BytesIO(screenshot_png))
        palette = thief.get_palette(color_count=_BRAND_COLOR_COUNT, quality=10)
    except (OSError, ValueError) as e:
        log.warning("html_only.colorthief_failed", error=str(e))
        return []
    return [_rgb_to_hex(rgb) for rgb in palette]


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"#{r:02X}{g:02X}{b:02X}"


# ── Visual: logo + hero discovery and upload ────────────────────────────────


def _upload_logo(soup: BeautifulSoup, page_url: str) -> str | None:
    candidate = _find_logo_candidate(soup, page_url)
    if not candidate:
        return None
    return _fetch_and_upload(candidate, page_url, asset_name="logo")


def _upload_hero(soup: BeautifulSoup, page_url: str) -> str | None:
    candidate = _find_hero_candidate(soup, page_url)
    if not candidate:
        return None
    return _fetch_and_upload(candidate, page_url, asset_name="hero")


def _find_logo_candidate(soup: BeautifulSoup, page_url: str) -> str | None:
    header = soup.find(["header", "nav"])
    scopes: list[Tag] = [header] if isinstance(header, Tag) else []

    for scope in scopes:
        for img in scope.find_all("img"):
            if not isinstance(img, Tag):
                continue
            if _img_looks_like_logo(img):
                src = _img_src(img, page_url)
                if src and not _is_tracking_image_url(src):
                    return src

    for scope in scopes:
        first_img = scope.find("img")
        if isinstance(first_img, Tag):
            src = _img_src(first_img, page_url)
            if src and not _is_tracking_image_url(src):
                return src

    icon = soup.find("link", rel=re.compile(r"icon", re.I))
    if isinstance(icon, Tag):
        href = icon.get("href")
        if isinstance(href, str) and href.strip():
            return urljoin(page_url, href.strip())

    return None


def _find_hero_candidate(soup: BeautifulSoup, page_url: str) -> str | None:
    skip_scopes: list[Tag] = []
    for tag_name in ("header", "nav", "footer"):
        for found in soup.find_all(tag_name):
            if isinstance(found, Tag):
                skip_scopes.append(found)

    def in_skip_scope(el: Tag) -> bool:
        for scope in skip_scopes:
            if el in scope.descendants:
                return True
        return False

    candidates: list[tuple[int, str]] = []
    for img in soup.find_all("img"):
        if not isinstance(img, Tag):
            continue
        if in_skip_scope(img):
            continue
        if _img_looks_like_logo(img):
            continue
        src = _img_src(img, page_url)
        if not src or _is_tracking_image_url(src):
            continue
        area = _declared_area(img)
        candidates.append((area, src))

    if not candidates:
        return None

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return candidates[0][1]


def _img_looks_like_logo(img: Tag) -> bool:
    for attr in ("src", "alt", "id", "class"):
        value = img.get(attr)
        text: Iterable[str]
        if isinstance(value, list):
            text = value
        elif isinstance(value, str):
            text = (value,)
        else:
            continue
        for s in text:
            if "logo" in s.lower():
                return True
    return False


def _is_tracking_image_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host in _TRACKING_HOSTS:
        return True
    for tracked in _TRACKING_HOSTS:
        if host.endswith("." + tracked):
            return True
    if host in ("facebook.com", "www.facebook.com") and parsed.path.startswith("/tr"):
        return True
    return False


def _img_src(img: Tag, page_url: str) -> str | None:
    for attr in ("src", "data-src", "data-lazy-src", "data-original"):
        value = img.get(attr)
        if isinstance(value, str) and value.strip():
            return urljoin(page_url, value.strip())
    return None


def _declared_area(img: Tag) -> int:
    width = _safe_int_attr(img.get("width"))
    height = _safe_int_attr(img.get("height"))
    if width and height:
        return width * height
    if width:
        return width
    if height:
        return height
    return 0


def _safe_int_attr(value: object) -> int:
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return 0


def _fetch_and_upload(candidate_url: str, page_url: str, *, asset_name: str) -> str | None:
    try:
        fetched = fetch_image(candidate_url)
    except (ImageFetchError, UnsafeUrlError, httpx.HTTPError) as e:
        log.warning(
            "html_only.image_fetch_failed",
            asset=asset_name,
            url=candidate_url,
            error=str(e),
        )
        return None

    domain = canonicalize_domain(page_url)
    key = f"extractions/{domain}/{asset_name}.{fetched.extension}"

    try:
        return r2.upload_bytes(key, fetched.body, fetched.content_type)
    except (r2.R2ConfigError, r2.R2UploadError) as e:
        log.warning(
            "html_only.image_upload_failed",
            asset=asset_name,
            key=key,
            error=str(e),
        )
        return None
