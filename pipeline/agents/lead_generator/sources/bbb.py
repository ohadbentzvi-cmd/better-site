"""BBB.org scraper.

Two-step flow:

1. SEARCH PAGE — lists ~15 businesses per page for (vertical, city, state).
   We parse business name, phone, address, BBB rating, accreditation,
   and the profile URL from each card.

2. PROFILE PAGE — one per business. Only place the website URL lives.
   We prefer structured JSON-LD (``schema.org/LocalBusiness``) and fall
   back to scanning external links on the page.

Design choices — see ``docs/lead_generator.md`` for the full walkthrough.

- **Plain HTTP GET**, no Playwright. BBB server-renders; a realistic
  User-Agent + identifiable contact URL is enough.
- **Single ``httpx.AsyncClient`` per run** so cookies + keep-alive persist.
- **CSS selectors, not DOM walking.** One fixture test fails loudly the
  day BBB changes their markup (rather than silently returning 0 leads).
- **Sequential profile fetches** for v1. Concurrency is a post-MVP knob.
- **``tenacity`` retries** with exponential backoff on transport errors
  and 429s; 403 raises ``BBBBlockedError`` to halt the batch.
- **Explicit exception hierarchy.** No catch-all ``except Exception``.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus, urljoin

import httpx
import structlog
from bs4 import BeautifulSoup, Tag
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from pipeline.agents.lead_generator.base import RawLead

log = structlog.get_logger(__name__)

BBB_BASE = "https://www.bbb.org"

DEFAULT_HEADERS = {
    "User-Agent": "BetterSiteBot/0.1 (+https://bettersite.co/bot)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.bbb.org/",
}

# Internal vertical tag → BBB search query
VERTICAL_QUERY: dict[str, str] = {
    "movers": "moving companies",
    # future: "lawyers": "law firms", "cleaners": "cleaning services", ...
}

# Consecutive empty-after-dedup pages that signal a city is exhausted.
_ZERO_NEW_STREAK_STOP = 3

# Courteous per-request jitter (seconds). Kept small; BBB doesn't complain
# at this rate from a single IP.
_REQUEST_JITTER = (0.3, 0.8)


# ── Exceptions ───────────────────────────────────────────────────────────────


class BBBError(Exception):
    """Base for all BBB-scraper errors."""


class BBBRateLimitError(BBBError):
    """429 from BBB — retryable."""


class BBBBlockedError(BBBError):
    """403 from BBB — batch should halt, not be silently retried."""


class BBBParseError(BBBError):
    """Unexpected HTML structure. Skip the row, log, continue."""


# ── Intermediate data ────────────────────────────────────────────────────────


@dataclass
class ProfileStub:
    """What the search page gives us. Missing website_url; profile fetch fills it."""

    name: str
    profile_url: str
    phone: str | None
    address_raw: str | None
    bbb_rating: str | None
    accredited: bool


@dataclass
class ProfileDetail:
    """What the profile page adds."""

    website_url: str | None
    email: str | None
    years_in_business: str | None


# ── Source ───────────────────────────────────────────────────────────────────


class BBBSource:
    """``LeadSource`` implementation for bbb.org."""

    name = "bbb"

    async def fetch(
        self,
        *,
        vertical: str,
        state: str,
        city: str,
        max_pages: int | None = None,
    ) -> AsyncIterator[RawLead]:
        query = VERTICAL_QUERY.get(vertical)
        if query is None:
            raise ValueError(
                f"no BBB search query registered for vertical {vertical!r}; "
                f"add it to pipeline.agents.lead_generator.sources.bbb.VERTICAL_QUERY"
            )

        seen_profile_urls: set[str] = set()
        zero_new_streak = 0

        async with _bbb_client() as client:
            page = 1
            while True:
                if max_pages is not None and page > max_pages:
                    log.info("bbb.pagination.max_pages_reached", page=page, max_pages=max_pages)
                    break

                log.info(
                    "bbb.search.page_start",
                    vertical=vertical,
                    state=state,
                    city=city,
                    page=page,
                )
                try:
                    stubs = await _fetch_search_page(
                        client, query=query, state=state, city=city, page=page
                    )
                except BBBBlockedError:
                    log.error("bbb.search.blocked", page=page)
                    raise

                if not stubs:
                    log.info("bbb.search.empty_page", page=page)
                    break

                new_stubs = [s for s in stubs if s.profile_url not in seen_profile_urls]
                seen_profile_urls.update(s.profile_url for s in new_stubs)

                if not new_stubs:
                    zero_new_streak += 1
                    log.info(
                        "bbb.search.page_all_duplicates",
                        page=page,
                        zero_new_streak=zero_new_streak,
                    )
                    if zero_new_streak >= _ZERO_NEW_STREAK_STOP:
                        log.info("bbb.search.city_exhausted", page=page)
                        break
                else:
                    zero_new_streak = 0

                log.info(
                    "bbb.search.page_complete",
                    page=page,
                    stubs_on_page=len(stubs),
                    new_stubs=len(new_stubs),
                )

                for stub in new_stubs:
                    try:
                        detail = await _fetch_profile(client, stub)
                    except BBBBlockedError:
                        log.error("bbb.profile.blocked", profile_url=stub.profile_url)
                        raise
                    except BBBParseError as e:
                        log.warning(
                            "bbb.profile.parse_error",
                            profile_url=stub.profile_url,
                            error=str(e),
                        )
                        continue

                    if not detail.website_url:
                        log.info(
                            "bbb.profile.no_website",
                            profile_url=stub.profile_url,
                            business_name=stub.name,
                        )
                        continue

                    yield _to_raw_lead(
                        vertical=vertical,
                        state=state,
                        city=city,
                        stub=stub,
                        detail=detail,
                    )

                page += 1


# ── HTTP client ──────────────────────────────────────────────────────────────


def _bbb_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=BBB_BASE,
        headers=DEFAULT_HEADERS,
        timeout=httpx.Timeout(15.0, connect=5.0),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        http2=True,
        follow_redirects=True,
    )


async def _get_with_retries(client: httpx.AsyncClient, url: str) -> httpx.Response:
    """GET with tenacity-backed retries + rate-limit awareness."""
    await asyncio.sleep(random.uniform(*_REQUEST_JITTER))

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.TransportError, BBBRateLimitError)),
        reraise=True,
    ):
        with attempt:
            response = await client.get(url)
            if response.status_code == 429:
                retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                log.warning("bbb.rate_limited", url=url, retry_after=retry_after)
                await asyncio.sleep(retry_after)
                raise BBBRateLimitError(f"429 on {url}")
            if response.status_code == 403:
                raise BBBBlockedError(f"403 on {url}")
            response.raise_for_status()
            return response
    raise BBBError(f"unreachable — retry exhausted for {url}")


def _parse_retry_after(value: str | None) -> float:
    if not value:
        return 30.0
    try:
        return float(value)
    except ValueError:
        return 30.0


# ── Search page ──────────────────────────────────────────────────────────────


async def _fetch_search_page(
    client: httpx.AsyncClient, *, query: str, state: str, city: str, page: int
) -> list[ProfileStub]:
    url = (
        f"/search?find_country=USA&find_text={quote_plus(query)}"
        f"&find_loc={quote_plus(f'{city}, {state}')}&page={page}"
    )
    response = await _get_with_retries(client, url)
    return list(parse_search_page(response.text))


def parse_search_page(html: str) -> Iterator[ProfileStub]:
    """Public for tests. Given raw HTML, yield ``ProfileStub`` per card.

    Selector strategy — match on ``a[href*='/profile/']`` anywhere on the
    page, then walk up to the nearest card-ish container for siblings
    (phone, address, rating). BBB's card CSS class has changed multiple
    times historically, but the profile-link shape is stable.
    """
    soup = BeautifulSoup(html, "lxml")
    profile_links = soup.select("a[href*='/profile/']")
    if not profile_links:
        return

    seen_on_page: set[str] = set()
    for link in profile_links:
        href = link.get("href") or ""
        if not href.startswith("/") and BBB_BASE not in href:
            continue
        profile_url = urljoin(BBB_BASE, href)
        if profile_url in seen_on_page:
            continue
        seen_on_page.add(profile_url)

        name = link.get_text(strip=True)
        if not name or _looks_like_ui_artifact(name):
            continue

        card = _nearest_card_container(link)
        card_text = card.get_text(" ", strip=True) if card else ""
        yield ProfileStub(
            name=name,
            profile_url=profile_url,
            phone=_extract_phone(card_text),
            address_raw=_extract_address_raw(card, card_text),
            bbb_rating=_extract_rating(card),
            accredited=_extract_accredited(card),
        )


_UI_ARTIFACT_LITERALS = frozenset(
    {
        "view hq",
        "view hq business profile",
        "view hq profile",
        "hq business profile",
        "get a quote",
        "get quote",
        "request a quote",
        "learn more",
        "visit website",
        "view profile",
        "view business profile",
        "claim this business",
        "more service areas",
        "moreservice areas",  # seen in the wild; BBB renders without the space
        "service areas",
        "see all locations",
        "see more locations",
        "additional locations",
    }
)


def _looks_like_ui_artifact(name: str) -> bool:
    cleaned = name.strip().lower()
    if cleaned in _UI_ARTIFACT_LITERALS:
        return True
    # Catch common prefixes that survive whitespace-collapse edge cases.
    for prefix in ("view hq", "moreservice", "more service"):
        if cleaned.startswith(prefix):
            return True
    return False


def _nearest_card_container(link: Tag) -> Tag | None:
    """Walk up to the nearest likely card root. Bounded to 6 hops.

    "card" / "listing" in the class name are the reliable markers; "result"
    alone is too loose (``result-title`` is inside the card, not around it).
    Sub-containers like ``result-title`` are explicitly skipped.
    """
    node: Tag | None = link
    for _ in range(6):
        if node is None:
            return None
        cls = " ".join(node.get("class") or []).lower()
        if any(sub in cls for sub in ("title", "header", "link")):
            node = node.parent if isinstance(node.parent, Tag) else None
            continue
        if "card" in cls or "listing" in cls:
            return node
        node = node.parent if isinstance(node.parent, Tag) else None
    return link.parent if isinstance(link.parent, Tag) else None


_PHONE_RE = re.compile(r"\(\d{3}\)\s*\d{3}[-.\s]\d{4}")


def _extract_phone(card_text: str) -> str | None:
    m = _PHONE_RE.search(card_text)
    return m.group(0) if m else None


def _extract_address_raw(card: Tag | None, card_text: str) -> str | None:
    if card is None:
        return None
    # Prefer structured element when present.
    for sel in (".address", ".street-address", "[itemprop=address]"):
        el = card.select_one(sel)
        if el:
            text = el.get_text(" ", strip=True)
            if text:
                return text
    # Fallback: text between phone and end of ZIP+4 / 5-digit ZIP.
    m = re.search(
        r"\(\d{3}\)\s*\d{3}[-.\s]\d{4}\s*(.+?\b\d{5}(?:-\d{4})?\b)",
        card_text,
    )
    return m.group(1).strip() if m else None


def _extract_rating(card: Tag | None) -> str | None:
    if card is None:
        return None
    for sel in (".bbb-rating", "[class*=rating]"):
        el = card.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            if text and len(text) <= 3:  # "A+", "A", "B+", ...
                return text
    return None


def _extract_accredited(card: Tag | None) -> bool:
    if card is None:
        return False
    for sel in (".accredited-badge", "[class*=accredit]"):
        if card.select_one(sel):
            return True
    text = card.get_text(" ", strip=True).lower()
    return "bbb accredited" in text


# ── Profile page ─────────────────────────────────────────────────────────────


async def _fetch_profile(
    client: httpx.AsyncClient, stub: ProfileStub
) -> ProfileDetail:
    log.info("bbb.profile.fetch_start", profile_url=stub.profile_url)
    response = await _get_with_retries(client, stub.profile_url)
    detail = parse_profile_page(response.text)
    log.info(
        "bbb.profile.fetch_complete",
        profile_url=stub.profile_url,
        website_found=bool(detail.website_url),
    )
    return detail


def parse_profile_page(html: str) -> ProfileDetail:
    """Public for tests. Extract website + email from a BBB profile page."""
    soup = BeautifulSoup(html, "lxml")

    website = _website_from_json_ld(soup) or _website_from_links(soup)
    email = _email_from_page(soup)
    years = _years_in_business(soup)

    return ProfileDetail(website_url=website, email=email, years_in_business=years)


def _website_from_json_ld(soup: BeautifulSoup) -> str | None:
    for script in soup.select("script[type='application/ld+json']"):
        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue
        try:
            data: Any = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for candidate in _json_ld_candidates(data):
            if isinstance(candidate, dict):
                url = candidate.get("url")
                if isinstance(url, str) and _is_external_url(url):
                    return url
    return None


def _json_ld_candidates(data: Any) -> Iterator[Any]:
    if isinstance(data, list):
        for item in data:
            yield from _json_ld_candidates(item)
    else:
        yield data


_EXTERNAL_LINK_TEXT = ("visit website", "website", "visit site")


def _website_from_links(soup: BeautifulSoup) -> str | None:
    for a in soup.select("a[href^='http']"):
        href = a.get("href") or ""
        if not _is_external_url(href):
            continue
        text = a.get_text(strip=True).lower()
        rel = " ".join(a.get("rel") or [])
        if any(w in text for w in _EXTERNAL_LINK_TEXT) or "external" in rel:
            return href
    return None


def _is_external_url(url: str) -> bool:
    url = (url or "").lower()
    if not url.startswith(("http://", "https://")):
        return False
    return "bbb.org" not in url


_EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.IGNORECASE)


def _email_from_page(soup: BeautifulSoup) -> str | None:
    # mailto link first.
    a = soup.select_one("a[href^='mailto:']")
    if a:
        href = a.get("href") or ""
        addr = href[len("mailto:") :].split("?")[0].strip()
        if addr:
            return addr.lower()
    # Visible email in copy (rare, but worth grabbing).
    text = soup.get_text(" ", strip=True)
    m = _EMAIL_RE.search(text)
    return m.group(0).lower() if m else None


_YEARS_RE = re.compile(r"years in business[:\s]*([0-9]+)", re.IGNORECASE)


def _years_in_business(soup: BeautifulSoup) -> str | None:
    text = soup.get_text(" ", strip=True)
    m = _YEARS_RE.search(text)
    return m.group(1) if m else None


# ── Assembly ─────────────────────────────────────────────────────────────────


def _to_raw_lead(
    *,
    vertical: str,
    state: str,
    city: str,
    stub: ProfileStub,
    detail: ProfileDetail,
) -> RawLead:
    metadata: dict[str, Any] = {
        "bbb_profile_url": stub.profile_url,
        "bbb_rating": stub.bbb_rating,
        "accredited": stub.accredited,
        "address_raw": stub.address_raw,
    }
    if detail.years_in_business:
        metadata["years_in_business"] = detail.years_in_business
    # Drop None-valued keys so the JSONB stays tidy.
    metadata = {k: v for k, v in metadata.items() if v is not None and v != ""}

    return RawLead(
        business_name=stub.name,
        website_url=detail.website_url or "",
        vertical=vertical,
        country="US",
        state=state,
        city=city,
        phone=stub.phone,
        email=detail.email,
        email_source="bbb" if detail.email else None,
        address=stub.address_raw,
        source="bbb",
        source_metadata=metadata,
    )


__all__ = [
    "BBBSource",
    "BBBError",
    "BBBBlockedError",
    "BBBRateLimitError",
    "BBBParseError",
    "parse_search_page",
    "parse_profile_page",
    "ProfileStub",
    "ProfileDetail",
]
