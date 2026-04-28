"""Shared Playwright fetch helpers.

Both the Scanner (which extracts DOM + visibility signals for scoring) and
the Extractor (which pulls content for site rebuild) need to render pages
and take screenshots. The shared knowledge sits here:

- Two-tier navigation (`load` -> `domcontentloaded` fallback) — the primary
  ``load`` wait is NOT blocked by analytics or chat widgets that keep
  ``networkidle`` busy forever.
- Viewport sizes for desktop + mobile.
- Conservative cleanup so a crashed page never leaks a chromium process.

Two layers of API:

- :func:`navigate_safely` — building block. Scanner uses this directly so
  it can run its own ``page.evaluate`` JS for visibility/computed-style
  signals that static HTML can't provide.
- :func:`render_page` — high-level helper for callers that only need raw
  HTML + screenshots (the Extractor).
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog
from playwright.async_api import (
    Browser,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

log = structlog.get_logger(__name__)

DESKTOP_VIEWPORT = {"width": 1280, "height": 900}
MOBILE_VIEWPORT = {"width": 375, "height": 812}

# Nav timeouts:
#   - Primary ``load`` is generous; many SMB sites are slow.
#   - Fallback ``domcontentloaded`` is shorter — if we're already past the
#     load timeout, we just want SOMETHING parseable before giving up.
#   - Settle is best-effort; lets late images paint into the screenshot.
NAV_TIMEOUT_MS = 30_000
FALLBACK_NAV_TIMEOUT_MS = 15_000
POST_LOAD_SETTLE_MS = 3_000


class BrowserFetchError(Exception):
    """Both ``load`` and ``domcontentloaded`` timed out, or chromium crashed.

    Caller decides whether to skip the URL, emit an event, or retry.
    """


@dataclass(frozen=True)
class RenderedPage:
    """Raw materials produced by :func:`render_page`.

    ``html`` is the post-render DOM (after JS executed). ``desktop_png`` and
    ``mobile_png`` are full-page screenshots at their respective viewports.
    Callers downstream are responsible for any further parsing or upload.
    """

    url: str
    html: str
    desktop_png: bytes
    mobile_png: bytes


async def navigate_safely(page: Page, url: str) -> None:
    """Two-tier navigation with best-effort settle.

    Primary: wait for ``load`` (all initial resources). NOT ``networkidle``
    — that's blocked indefinitely by analytics + live-chat widgets.

    Fallback on timeout: ``domcontentloaded`` so we still get DOM + a
    screenshot on pathological sites (badly-served CSS, hung third-party
    script, etc.).

    Settle: short ``networkidle`` wait so late-loading images make it into
    the screenshot. Swallows its own timeout — analytics traffic is
    expected.

    Raises:
        BrowserFetchError: when both ``load`` and the ``domcontentloaded``
            fallback time out.
    """
    try:
        await page.goto(url, wait_until="load", timeout=NAV_TIMEOUT_MS)
    except PlaywrightTimeoutError as e:
        log.info("browser.goto_load_timeout_fallback", url=url, error=str(e))
        try:
            await page.goto(
                url, wait_until="domcontentloaded", timeout=FALLBACK_NAV_TIMEOUT_MS
            )
        except PlaywrightTimeoutError as inner:
            raise BrowserFetchError(
                f"both load and domcontentloaded timed out for {url}"
            ) from inner

    try:
        await page.wait_for_load_state("networkidle", timeout=POST_LOAD_SETTLE_MS)
    except PlaywrightTimeoutError:
        # Expected on sites with ongoing analytics. Not an error.
        pass


async def render_page(url: str) -> RenderedPage:
    """Launch chromium, render ``url`` at desktop + mobile, return raw output.

    Caller is responsible for SSRF-checking ``url`` before calling.

    Raises:
        BrowserFetchError: page is genuinely unreachable (both nav strategies
            timed out, or chromium crashed).
    """
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                return await _render(pw, browser, url)
            finally:
                await browser.close()
    except BrowserFetchError:
        raise
    except PlaywrightTimeoutError as e:
        # Top-level timeout outside navigate_safely (e.g. context creation).
        raise BrowserFetchError(f"playwright timeout for {url}: {e}") from e


async def _render(_pw: Playwright, browser: Browser, url: str) -> RenderedPage:
    desktop_ctx = await browser.new_context(viewport=DESKTOP_VIEWPORT)
    try:
        desktop_page = await desktop_ctx.new_page()
        await navigate_safely(desktop_page, url)
        html = await desktop_page.content()
        desktop_png = await desktop_page.screenshot(full_page=True, type="png")
    finally:
        await desktop_ctx.close()

    mobile_ctx = await browser.new_context(viewport=MOBILE_VIEWPORT)
    try:
        mobile_page = await mobile_ctx.new_page()
        await navigate_safely(mobile_page, url)
        mobile_png = await mobile_page.screenshot(full_page=True, type="png")
    finally:
        await mobile_ctx.close()

    return RenderedPage(
        url=url,
        html=html,
        desktop_png=desktop_png,
        mobile_png=mobile_png,
    )


__all__ = [
    "BrowserFetchError",
    "DESKTOP_VIEWPORT",
    "FALLBACK_NAV_TIMEOUT_MS",
    "MOBILE_VIEWPORT",
    "NAV_TIMEOUT_MS",
    "POST_LOAD_SETTLE_MS",
    "RenderedPage",
    "navigate_safely",
    "render_page",
]
