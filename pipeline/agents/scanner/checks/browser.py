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

# Nav strategy:
#   - Primary: wait for the ``load`` event (all initial resources done).
#     Unlike ``networkidle``, this is NOT blocked by long-polling analytics,
#     live-chat widgets, or ads that keep the network busy forever.
#   - Fallback on timeout: ``domcontentloaded`` (DOM parsed, before images /
#     CSS finish) so we still get DOM + a screenshot on pathological sites.
#   - Best-effort short ``networkidle`` wait after load to let late images
#     paint into the screenshot. Swallows its own timeout.
NAV_TIMEOUT_MS = 30_000
FALLBACK_NAV_TIMEOUT_MS = 15_000
POST_LOAD_SETTLE_MS = 3_000

# "Above the fold" threshold for desktop. 900px mirrors viewport height;
# elements with bounding box top < this are visible on first paint.
ABOVE_FOLD_PX = 900


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
    await _navigate_safely(desktop_page, url)
    desktop_shot = await desktop_page.screenshot(full_page=True, type="png")

    title = await desktop_page.title()
    meta = await _extract_meta(desktop_page)
    headings = await _extract_headings(desktop_page)
    images = await _extract_image_alts(desktop_page)
    json_ld_types = await _extract_json_ld_types(desktop_page)
    conversion = await _extract_conversion_signals(desktop_page)

    await desktop_context.close()

    # ── Mobile pass: screenshot only. Viewport meta is DOM, already captured.
    mobile_context = await browser.new_context(viewport=MOBILE_VIEWPORT)
    mobile_page = await mobile_context.new_page()
    await _navigate_safely(mobile_page, url)
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
        phone_above_fold=conversion["phone_above_fold"],
        phone_text=conversion["phone_text"],
        cta_above_fold=conversion["cta_above_fold"],
        cta_text=conversion["cta_text"],
        has_contact_form=conversion["has_contact_form"],
        copyright_year=conversion["copyright_year"],
        has_reviews_or_testimonials=conversion["has_reviews_or_testimonials"],
        desktop_screenshot_png=desktop_shot,
        mobile_screenshot_png=mobile_shot,
    )


async def _navigate_safely(page: Any, url: str) -> None:
    """Two-tier ``page.goto`` with best-effort settle.

    Primary: wait for ``load`` — NOT blocked by analytics/chat widgets
    that keep ``networkidle`` permanently busy.
    Fallback: ``domcontentloaded`` so we still get DOM + screenshot on
    pathological sites (badly-served CSS, hung third-party script, etc.).
    Settle: short best-effort ``networkidle`` wait so late images make
    it into the screenshot. Swallows its own timeout.
    """
    try:
        await page.goto(url, wait_until="load", timeout=NAV_TIMEOUT_MS)
    except PlaywrightTimeoutError as e:
        log.info(
            "browser.goto_load_timeout_fallback_domcontentloaded",
            url=url,
            error=str(e),
        )
        await page.goto(url, wait_until="domcontentloaded", timeout=FALLBACK_NAV_TIMEOUT_MS)

    try:
        await page.wait_for_load_state("networkidle", timeout=POST_LOAD_SETTLE_MS)
    except PlaywrightTimeoutError:
        # Expected on sites with ongoing analytics. Not an error.
        pass


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


async def _extract_conversion_signals(page: Any) -> dict[str, Any]:
    """Above-the-fold + site-wide conversion heuristics.

    One JS round-trip returns everything: phone visibility near the top,
    CTA-ish button/link visibility near the top, form presence anywhere,
    max copyright year, and cheap trust-signal indicators.
    """
    return await page.evaluate(
        """(threshold) => {
          const isVisible = (el) => {
            const r = el.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) return false;
            const cs = window.getComputedStyle(el);
            if (cs.visibility === 'hidden' || cs.display === 'none') return false;
            if (parseFloat(cs.opacity) === 0) return false;
            return true;
          };
          const topOf = (el) => el.getBoundingClientRect().top + window.scrollY;

          // ── Phone above the fold ──
          const PHONE_RE = /(\\+?\\d[\\d\\s\\-().]{7,}\\d)/;
          let phone_above_fold = false;
          let phone_text = null;
          for (const a of document.querySelectorAll("a[href^='tel:']")) {
            if (!isVisible(a)) continue;
            if (topOf(a) < threshold) {
              phone_above_fold = true;
              phone_text = (a.textContent || a.href.replace('tel:', '')).trim();
              break;
            }
          }
          if (!phone_above_fold) {
            // Fallback: visible text containing a phone-shaped string near top.
            const candidates = document.querySelectorAll("header, nav, [class*='header'], [class*='top-bar']");
            for (const c of candidates) {
              if (!isVisible(c)) continue;
              if (topOf(c) >= threshold) continue;
              const m = PHONE_RE.exec(c.textContent || '');
              if (m) { phone_above_fold = true; phone_text = m[0].trim(); break; }
            }
          }

          // ── CTA above the fold ──
          const CTA_KEYWORDS = [
            "get a quote", "get quote", "request a quote", "request quote",
            "free estimate", "free quote", "book now", "book online", "schedule",
            "contact us", "get started", "call now", "request service",
            "get a free", "request a free",
          ];
          const CTA_SINGLE_WORDS = ["quote", "book", "schedule", "contact", "call"];
          let cta_above_fold = false;
          let cta_text = null;
          const clickables = [
            ...document.querySelectorAll("a, button, [role='button']"),
          ];
          for (const el of clickables) {
            if (!isVisible(el)) continue;
            if (topOf(el) >= threshold) continue;
            const text = (el.textContent || '').trim().toLowerCase();
            if (!text || text.length > 60) continue;
            if (CTA_KEYWORDS.some(k => text.includes(k))
                || CTA_SINGLE_WORDS.some(w => new RegExp(`\\\\b${w}\\\\b`).test(text))) {
              cta_above_fold = true;
              cta_text = (el.textContent || '').trim().slice(0, 80);
              break;
            }
          }

          // ── Contact form anywhere on the page ──
          let has_contact_form = false;
          for (const f of document.querySelectorAll("form")) {
            const inputs = f.querySelectorAll("input, textarea");
            const hasTextLike = [...inputs].some(i => {
              const t = (i.type || 'text').toLowerCase();
              return ["text", "email", "tel", "textarea"].includes(t);
            });
            if (hasTextLike) { has_contact_form = true; break; }
          }

          // ── Max copyright year found in visible text ──
          const bodyText = (document.body && document.body.innerText) || "";
          let copyright_year = null;
          const cpRe = /(?:©|&copy;|copyright)[^\\d]{0,20}((?:19|20)\\d{2})/gi;
          let m;
          while ((m = cpRe.exec(bodyText)) !== null) {
            const y = parseInt(m[1], 10);
            if (!isNaN(y) && (copyright_year === null || y > copyright_year)) {
              copyright_year = y;
            }
          }

          // ── Reviews / testimonials signals ──
          let has_reviews_or_testimonials = false;
          const jsonldBlocks = [...document.querySelectorAll("script[type='application/ld+json']")]
              .map(s => (s.textContent || '').toLowerCase());
          if (jsonldBlocks.some(b => b.includes('"review"') || b.includes('"aggregaterating"'))) {
            has_reviews_or_testimonials = true;
          }
          if (!has_reviews_or_testimonials) {
            const lower = bodyText.toLowerCase();
            if (lower.includes("testimonial") || lower.includes("★★★★")
                || /\\b5\\s*stars?\\b/i.test(lower)
                || /\\b5\\s*\\/\\s*5\\b/i.test(lower)) {
              has_reviews_or_testimonials = true;
            }
          }

          return {
            phone_above_fold,
            phone_text,
            cta_above_fold,
            cta_text,
            has_contact_form,
            copyright_year,
            has_reviews_or_testimonials,
          };
        }""",
        ABOVE_FOLD_PX,
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
