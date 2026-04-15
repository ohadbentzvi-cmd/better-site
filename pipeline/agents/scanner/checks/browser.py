"""Playwright-based DOM + screenshot check.

One browser session per URL extracts everything we need from rendered
HTML: meta tags, heading structure, image alts, JSON-LD types, plus
desktop + mobile screenshots.

Playwright/Chromium crashes are caught and turned into
``BrowserCheckResult(available=False, error_reason=...)`` so scoring can
degrade gracefully — we never let one bad site kill a whole run.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from playwright.async_api import (
    Browser,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from pipeline.agents.scanner.base import BrowserCheckResult

log = structlog.get_logger(__name__)

DESKTOP_VIEWPORT = {"width": 1280, "height": 900}
MOBILE_VIEWPORT = {"width": 375, "height": 812}

NAV_TIMEOUT_MS = 30_000  # 30s hard cap per page load


async def fetch_browser_data(url: str) -> BrowserCheckResult:
    """Run Playwright against ``url``. Always returns a result; never raises."""
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                return await _extract(pw, browser, url)
            finally:
                await browser.close()
    except PlaywrightTimeoutError as e:
        log.warning("browser.timeout", url=url, error=str(e))
        return BrowserCheckResult(available=False, error_reason=f"timeout: {e}")
    except Exception as e:  # noqa: BLE001 — Playwright surfaces many types
        log.warning("browser.failed", url=url, error=str(e), exc_info=True)
        return BrowserCheckResult(available=False, error_reason=str(e))


async def _extract(
    _pw: Playwright, browser: Browser, url: str
) -> BrowserCheckResult:
    # ── Desktop pass: screenshot + DOM extraction ───────────────────────────
    desktop_context = await browser.new_context(viewport=DESKTOP_VIEWPORT)
    desktop_page = await desktop_context.new_page()
    await desktop_page.goto(url, wait_until="networkidle", timeout=NAV_TIMEOUT_MS)
    desktop_shot = await desktop_page.screenshot(full_page=True, type="png")

    title = await desktop_page.title()
    meta = await _extract_meta(desktop_page)
    headings = await _extract_headings(desktop_page)
    images = await _extract_image_alts(desktop_page)
    json_ld_types = await _extract_json_ld_types(desktop_page)

    await desktop_context.close()

    # ── Mobile pass: screenshot only. Viewport meta is DOM, already captured.
    mobile_context = await browser.new_context(viewport=MOBILE_VIEWPORT)
    mobile_page = await mobile_context.new_page()
    await mobile_page.goto(url, wait_until="networkidle", timeout=NAV_TIMEOUT_MS)
    mobile_shot = await mobile_page.screenshot(full_page=True, type="png")
    await mobile_context.close()

    return BrowserCheckResult(
        title=title or None,
        meta_description=meta.get("description"),
        canonical_url=meta.get("canonical"),
        og_title=meta.get("og:title"),
        og_description=meta.get("og:description"),
        og_image=meta.get("og:image"),
        has_viewport_meta="viewport" in meta,
        viewport_content=meta.get("viewport"),
        h1_count=headings["h1"],
        h2_count=headings["h2"],
        h3_count=headings["h3"],
        heading_hierarchy_ok=headings["hierarchy_ok"],
        image_count=images["total"],
        images_with_alt=images["with_alt"],
        json_ld_types=json_ld_types,
        desktop_screenshot_png=desktop_shot,
        mobile_screenshot_png=mobile_shot,
    )


async def _extract_meta(page: Any) -> dict[str, str]:
    return await page.evaluate(
        """() => {
          const out = {};
          const desc = document.querySelector("meta[name='description']");
          if (desc && desc.content) out["description"] = desc.content;
          const canonical = document.querySelector("link[rel='canonical']");
          if (canonical && canonical.href) out["canonical"] = canonical.href;
          const viewport = document.querySelector("meta[name='viewport']");
          if (viewport && viewport.content) out["viewport"] = viewport.content;
          for (const prop of ["og:title", "og:description", "og:image"]) {
            const el = document.querySelector(`meta[property='${prop}']`);
            if (el && el.content) out[prop] = el.content;
          }
          return out;
        }"""
    )


async def _extract_headings(page: Any) -> dict[str, Any]:
    result = await page.evaluate(
        """() => {
          const levels = [...document.querySelectorAll("h1, h2, h3, h4, h5, h6")]
              .map(h => parseInt(h.tagName.substring(1)));
          const count = (n) => levels.filter(l => l === n).length;
          let hierarchy_ok = true;
          for (let i = 1; i < levels.length; i++) {
            if (levels[i] > levels[i - 1] + 1) { hierarchy_ok = false; break; }
          }
          return {
            h1: count(1), h2: count(2), h3: count(3),
            hierarchy_ok: hierarchy_ok,
          };
        }"""
    )
    return result


async def _extract_image_alts(page: Any) -> dict[str, int]:
    return await page.evaluate(
        """() => {
          const imgs = [...document.querySelectorAll("img")];
          const with_alt = imgs.filter(img => (img.alt || "").trim() !== "").length;
          return { total: imgs.length, with_alt: with_alt };
        }"""
    )


async def _extract_json_ld_types(page: Any) -> list[str]:
    raw_blocks = await page.evaluate(
        """() => [...document.querySelectorAll("script[type='application/ld+json']")]
                  .map(s => s.textContent || '')"""
    )
    types: list[str] = []
    for block in raw_blocks:
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        types.extend(_walk_types(data))
    # De-dupe while preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for t in types:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered


def _walk_types(data: Any) -> list[str]:
    found: list[str] = []
    if isinstance(data, list):
        for item in data:
            found.extend(_walk_types(item))
    elif isinstance(data, dict):
        t = data.get("@type")
        if isinstance(t, str):
            found.append(t)
        elif isinstance(t, list):
            found.extend(x for x in t if isinstance(x, str))
        # Recurse for nested @graph, itemOf, etc.
        for v in data.values():
            if isinstance(v, (dict, list)):
                found.extend(_walk_types(v))
    return found


__all__ = ["fetch_browser_data"]
