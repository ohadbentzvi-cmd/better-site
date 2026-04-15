# Website Scanner

How the Scanner works and how to add new inputs or scoring rules.

---

## Shape

```
┌────────────────────────────────────────────────────────────┐
│   Prefect flow: site-scan                                   │
│   inputs: urls? (list) OR limit? (for leads-table mode)     │
└────────────────────────┬───────────────────────────────────┘
                         │
                         ▼
         ┌──────────────────────────────┐
         │  ScanTarget.iter_targets()    │   ← Protocol, yields TargetUrl
         └──────────────┬───────────────┘
                        │
          ┌─────────────┴──────────────┐
          │                            │
 ┌────────────────────┐     ┌──────────────────────┐
 │ LeadTableTarget    │     │ UrlListTarget        │
 │ unscanned leads    │     │ explicit URLs; looks │
 │ from ops.leads     │     │ up lead_id by domain │
 └────────────────────┘     └──────────────────────┘
                        │
                        ▼
 ┌────────────────────────────────────────────────────────────┐
 │  scan_url(url)                                              │
 │   1. assert_safe_url (SSRF)                                 │
 │   2. PageSpeed Insights (mobile + desktop, async, parallel) │
 │      ┌────────────────────────────┐                         │
 │      │ concurrent with Playwright │                         │
 │      └────────────────────────────┘                         │
 │   3. Playwright session: screenshots + DOM extraction       │
 │   4. HTTP checks (robots, llms, sitemap, security headers)  │
 │   5. scoring.score_scan(...) -> per-dim scores + findings   │
 └────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
 ┌────────────────────────────────────────────────────────────┐
 │  if target.lead_id:                                         │
 │     UPSERT ops.scans (ON CONFLICT lead_id DO UPDATE)        │
 │  create per-URL markdown artifact (scaled screenshots)      │
 │  at end-of-run: create site-scan-summary artifact           │
 └────────────────────────────────────────────────────────────┘
```

**One abstraction boundary: `ScanTarget`.** Source of URLs is pluggable — anything that yields `TargetUrl` works. Everything downstream is target-agnostic.

---

## Conversion findings (no dimension score)

Orthogonal to the four dimensions. Six heuristics fire off the single Playwright session and produce `Finding(category="conversion")` entries in `issues_json` — designed as email-ready copy the Sales Agent can drop straight into cold emails.

- **Phone above the fold** — `tel:` link or phone regex in header/nav within first 900px.
- **CTA above the fold** — button/link with "quote / book / call / contact / schedule" language within first 900px.
- **Contact form anywhere** — any `<form>` with text/email/tel/textarea inputs.
- **Copyright year** — max 4-digit year in visible page text. Fires as "stale" when ≥2 years behind current year.
- **Reviews / testimonials** — JSON-LD `Review`/`AggregateRating` OR page text containing "testimonial" / "★★★★" / "5 stars".
- (HTTPS is already tracked as `has_ssl`; will be surfaced as a conversion finding later.)

These are intentionally **not scored**. A scalar "Conversion: 42" is weaker than a specific sentence. Example output seen on westheimertransfer.com:

> [medium/conversion] Your site's copyright says © 2013 — new visitors start to wonder if you're still in business.

## Scoring

Weighted composite of four dimensions. Locked weights:

| Dimension | Weight | Source |
|---|---|---|
| Performance | 45% | PageSpeed Insights mobile + desktop (mean of both Performance scores) |
| SEO | 20% | Browser DOM + HTTP checks (points-based, capped at 100) |
| AI-Readiness | 20% | Browser DOM + HTTP checks (points-based, capped at 100) |
| Security | 15% | HTTP response headers (fixed-point schedule, capped at 100) |

Overall = `round(0.45·perf + 0.20·seo + 0.20·ai + 0.15·sec)`.

**Partial scans.** Any dimension that can't be measured (e.g. PageSpeed API timed out) is recorded as `NULL`. In that case `overall` is also `NULL` and `scan_partial = true`. No silent rescaling — unknown is unknown.

**Findings** are the other half of the output. Each finding is pydantic:

```python
class Finding(BaseModel):
    category: "performance" | "seo" | "ai_readiness" | "security"
    severity: "high" | "medium" | "low"
    smb_message: str           # email-ready copy
    technical_detail: str      # for admin review
    evidence_url: str | None
```

The Sales Agent reads `issues_json` and drops `smb_message` strings straight into cold-email templates. Rules that produce findings live in `scoring.py` right next to the rule that fires them — one file to read, one place to rewrite copy.

---

## Checks

### PageSpeed Insights API (`checks/pagespeed.py`)

Two calls per URL — mobile and desktop strategies — fired concurrently via `asyncio.gather`. Uses `PAGESPEED_API_KEY` from the environment (free tier is 25k/day; without a key it falls back to 400/day from a single IP).

Extracts:
- Category scores: Performance, SEO, Best Practices.
- Core Web Vitals: LCP, FCP, CLS, TBT, TTFB, Speed Index.
- Page weight, unused CSS/JS scores, render-blocking score.

Retries: tenacity, 3 attempts, exponential backoff. On total failure (both strategies), `PageSpeedData.available = False`; scoring then marks the scan partial.

### Playwright session (`checks/browser.py`)

One headless Chromium session per URL. Two contexts:
- Desktop (1280×900): full-page screenshot + all DOM extraction.
- Mobile (375×812): full-page screenshot only.

DOM extracts: `<title>`, meta description, canonical URL, OG tags, viewport meta, H1/H2/H3 counts, heading-hierarchy OK flag, image alt coverage, JSON-LD `@type` values (walks nested `@graph` structures).

Any Playwright failure (timeout, crash, site blocking headless) → `BrowserCheckResult(available=False, error_reason=...)`. Scoring treats SEO + AI-Readiness as unmeasurable in that case and marks the scan partial.

### HTTP checks (`checks/http.py`)

Four sub-checks fired in parallel:

1. `GET /robots.txt` — present? `User-agent: *` + `Disallow: /` means `robots_blocks_all = true`.
2. `GET /llms.txt` — present?
3. `GET /sitemap.xml` + `GET /sitemap_index.xml` — count `<url>` entries.
4. `GET /` — read `Strict-Transport-Security`, `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`.

SSRF check runs once on the main URL in `pipeline.py` before any of these fire.

---

## Per-URL orchestration

```python
# pipeline/agents/scanner/pipeline.py:scan_url
pagespeed_task = asyncio.create_task(fetch_pagespeed(url, ...))   # Google hits the site
browser_result = await fetch_browser_data(url)                    # we hit the site
http_result = await fetch_http_checks(url)                        # we hit the site (but serial with browser)
pagespeed_result = await pagespeed_task                           # join back
```

PageSpeed runs on Google's servers — they hit the target from their IP, not us. So we kick it off in the background and let the browser session run concurrently. HTTP checks wait for the browser to finish, avoiding double-hammering the site from our own IP.

Per-URL runtime at POC scale: ~25-40s.

---

## Database

Scan results UPSERT into `ops.scans` keyed on `lead_id`. Columns used by this agent:

| Column | Notes |
|---|---|
| `lead_id` | UNIQUE → one scan per lead. ON CONFLICT triggers UPDATE. |
| `scanned_url` | The URL the scanner was given (may differ from `leads.website_url` later if we follow redirects). |
| `score` | Overall 0-100. `NULL` when `scan_partial=true`. |
| `pass_fail` | Populated as `score >= 70`. **Not used as a gate** — manual review only for POC. Dashboard convenience. |
| `score_{performance,seo,ai_readiness,security}` | Per-dimension scores. `NULL` when unmeasurable. |
| `pagespeed_mobile`, `pagespeed_desktop` | PageSpeed's own Performance category scores. |
| `pagespeed_available` | `false` when both strategies failed. |
| `scan_partial` | `true` when any dimension is `NULL`. |
| `raw_metrics` | JSONB: LCP, CLS, TBT, FCP, TTFB, page_weight, speed_index, etc. |
| `issues_json` | JSONB array of `Finding` dicts (SMB message + technical detail + severity). |
| `has_ssl`, `has_mobile`, `has_analytics` | Legacy booleans for admin UI. |
| `screenshot_r2_key` | Unused in Phase 2.5. Screenshots live in the Prefect artifact only. |

---

## Artifacts

Every run produces:

- **Per-URL markdown artifact** (one per scanned URL) — score table, findings sorted by severity, raw metrics block, scaled desktop + mobile screenshots (max 800px wide, JPEG q=80). Scaled in the flow so Prefect's UI renders quickly.
- **Run summary artifact** (`site-scan-summary`, one per run) — target mode, duration, distribution of overall scores across `{0-40, 40-70, 70-100, unknown}` buckets, top 5 most-common findings across the batch.

---

## Running

**Prefect UI:** the `site-scan` deployment runs with `urls=None, limit=50` (leads-mode). Trigger with a URL list via the parameter form for ad-hoc scans.

**CLI:**

```
python -m scripts.scan_urls --url https://westheimertransfer.com
python -m scripts.scan_urls --urls-file urls.txt
python -m scripts.scan_urls --from-leads --limit 20
```

---

## Adding a new target source

Same pattern as Lead Generator. Create a class that implements `ScanTarget`:

```python
class CustomTarget:
    name = "custom"
    async def iter_targets(self) -> AsyncIterator[TargetUrl]:
        ...
```

Then wire it up in the flow or pass a constructed instance to `run_scanner`.

---

## Adding a new scoring dimension

1. Add the column to `ops.scans` via an Alembic migration.
2. Update `pipeline/models/scan.py` to match.
3. Add a scoring function in `scoring.py` and call it from `score_scan`.
4. Add weight to the overall-score computation.
5. Add findings rules next to the scoring function.
6. Add a parametrized test case in `tests/unit/agents/scanner/test_scoring.py`.

---

## Testing

Fixtures in `tests/fixtures/scanner/` include two real PageSpeed response shapes (mobile + desktop). Parser tests exercise every field. Scoring tests are pure — given constructed pydantic inputs, assert scores and findings.

Playwright tests are deferred (running Chromium in CI is heavy). End-to-end smoke tests are manual for now:

```
python -m scripts.scan_urls --url https://example.com
```
