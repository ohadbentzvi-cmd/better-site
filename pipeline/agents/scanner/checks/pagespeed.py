"""PageSpeed Insights API client.

We fire two calls per URL (mobile + desktop). Each returns a rich
``lighthouseResult`` that we distill into a ``PageSpeedResult``. Failure
is graceful — parser returns ``None`` fields rather than raising, and the
outer ``fetch_pagespeed`` sets ``available=False`` on total failure so
scoring can mark the scan partial.

Rate limiting: a module-level semaphore + inter-request delay keeps us
under Google's quota (~25 req/100s free tier, higher with API key).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from pipeline.agents.scanner.base import PageSpeedData, PageSpeedResult

log = structlog.get_logger(__name__)

PAGESPEED_ENDPOINT = (
    "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
)
PAGESPEED_TIMEOUT_SECS = 60.0  # Google's own runs can take 30-45s

# Rate limiting: allow max 2 concurrent PageSpeed requests and enforce a
# minimum gap between requests to stay under Google's per-second quota.
_PAGESPEED_SEMAPHORE = asyncio.Semaphore(2)
_MIN_REQUEST_INTERVAL_SECS = 2.0  # ≤30 req/min ≈ safe for free tier
_last_request_time: float = 0.0
_rate_lock = asyncio.Lock()


async def _rate_limit() -> None:
    """Wait until at least ``_MIN_REQUEST_INTERVAL_SECS`` since the last request."""
    global _last_request_time
    async with _rate_lock:
        now = time.monotonic()
        elapsed = now - _last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL_SECS:
            await asyncio.sleep(_MIN_REQUEST_INTERVAL_SECS - elapsed)
        _last_request_time = time.monotonic()


class PageSpeedError(Exception):
    """Base for PageSpeed failures."""


class PageSpeedRateLimitError(PageSpeedError):
    """429 from Google. Retryable."""


async def fetch_pagespeed(url: str, *, api_key: str | None) -> PageSpeedData:
    """Fetch mobile + desktop PageSpeed for a URL. Graceful on failure."""
    mobile_task = _fetch_one(url, strategy="mobile", api_key=api_key)
    desktop_task = _fetch_one(url, strategy="desktop", api_key=api_key)
    mobile, desktop = await asyncio.gather(
        mobile_task, desktop_task, return_exceptions=True
    )

    mobile_result = _coerce(mobile, "mobile", url)
    desktop_result = _coerce(desktop, "desktop", url)
    available = mobile_result is not None or desktop_result is not None
    if not available:
        log.warning("pagespeed.both_strategies_failed", url=url)
    return PageSpeedData(mobile=mobile_result, desktop=desktop_result, available=available)


def _coerce(
    raw: PageSpeedResult | BaseException, strategy: str, url: str
) -> PageSpeedResult | None:
    if isinstance(raw, PageSpeedResult):
        return raw
    log.warning(
        "pagespeed.strategy_failed",
        url=url,
        strategy=strategy,
        error=str(raw),
    )
    return None


async def _fetch_one(
    url: str, *, strategy: str, api_key: str | None
) -> PageSpeedResult:
    params: dict[str, str] = {
        "url": url,
        "strategy": strategy,
        "category": "performance",
    }
    # PageSpeed accepts repeated category params; add the rest via a multi-dict.
    extra_categories = ["seo", "best-practices"]
    if api_key:
        params["key"] = api_key

    async with httpx.AsyncClient(timeout=PAGESPEED_TIMEOUT_SECS) as client:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=4, min=4, max=60),
            retry=retry_if_exception_type(
                (httpx.TransportError, PageSpeedRateLimitError)
            ),
            reraise=True,
        ):
            with attempt:
                async with _PAGESPEED_SEMAPHORE:
                    await _rate_limit()
                    query = [(k, v) for k, v in params.items()]
                    query.extend(("category", c) for c in extra_categories)
                    response = await client.get(PAGESPEED_ENDPOINT, params=query)
                if response.status_code == 429:
                    log.warning(
                        "pagespeed.rate_limited",
                        url=url,
                        strategy=strategy,
                        attempt=attempt.retry_state.attempt_number,
                    )
                    raise PageSpeedRateLimitError(f"429 on {url} / {strategy}")
                if response.status_code >= 500:
                    raise httpx.TransportError(
                        f"{response.status_code} from PageSpeed on {url}"
                    )
                response.raise_for_status()
                return parse_pagespeed_response(response.json(), strategy=strategy)
    raise PageSpeedError("unreachable — retry exhausted")


def parse_pagespeed_response(
    raw: dict[str, Any], *, strategy: str
) -> PageSpeedResult:
    """Pure parser — exposed for unit tests.

    Missing fields return ``None`` on the result; we never raise.
    """
    lighthouse = raw.get("lighthouseResult") or {}
    categories = lighthouse.get("categories") or {}
    audits = lighthouse.get("audits") or {}

    def cat_score(name: str) -> int | None:
        val = (categories.get(name) or {}).get("score")
        return int(round(val * 100)) if isinstance(val, (int, float)) else None

    def audit_num(name: str) -> float | None:
        val = (audits.get(name) or {}).get("numericValue")
        return float(val) if isinstance(val, (int, float)) else None

    def audit_score(name: str) -> float | None:
        val = (audits.get(name) or {}).get("score")
        return float(val) if isinstance(val, (int, float)) else None

    page_weight = audit_num("total-byte-weight")

    return PageSpeedResult(
        strategy=strategy,  # type: ignore[arg-type]
        performance_score=cat_score("performance"),
        seo_score=cat_score("seo"),
        best_practices_score=cat_score("best-practices"),
        lcp_ms=audit_num("largest-contentful-paint"),
        fcp_ms=audit_num("first-contentful-paint"),
        cls=audit_num("cumulative-layout-shift"),
        tbt_ms=audit_num("total-blocking-time"),
        ttfb_ms=audit_num("server-response-time"),
        speed_index_ms=audit_num("speed-index"),
        page_weight_bytes=int(page_weight) if page_weight is not None else None,
        unused_css_score=audit_score("unused-css-rules"),
        unused_js_score=audit_score("unused-javascript"),
        render_blocking_score=audit_score("render-blocking-resources"),
    )


__all__ = [
    "PageSpeedError",
    "PageSpeedRateLimitError",
    "fetch_pagespeed",
    "parse_pagespeed_response",
]
