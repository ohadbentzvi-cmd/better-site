# Lead Generator

How the BetterSite Lead Generator works, why it's shaped this way, and how to add another source.

---

## Shape

```
 ┌────────────────────────────────────────────────────────────┐
 │   Prefect flow: lead-generation                             │
 │   inputs: source, vertical, state, city, max_pages?         │
 └────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
          ┌──────────────────────────────┐
          │  LeadSource.fetch()          │     ← Protocol
          │  (registered in sources/)    │
          └──────────────────────────────┘
                          │ yields RawLead
                          ▼
 ┌────────────────────────────────────────────────────────────┐
 │  pipeline.py — source-agnostic                              │
 │  canonicalize URL → SSRF check → UPSERT ops.leads → event   │
 └────────────────────────────────────────────────────────────┘
                          │
                          ▼
                      ops.leads
                      ops.events
```

One abstraction boundary: `LeadSource`. Everything upstream of it (how we walk BBB, how we'd parse an FMCSA CSV dump) is source-specific. Everything downstream (normalization, dedup, UPSERT, audit) is source-agnostic and lives in `pipeline/agents/lead_generator/pipeline.py`.

**Adding a new source is one file plus one dict entry.** See [Adding a source](#adding-a-source) below.

---

## BBB source — detailed walkthrough

### Two-step fetch

**Step 1 — Search page.** Lists ~15 businesses per page for a `(vertical, city, state)` query.

```
https://www.bbb.org/search?find_country=USA&find_text=moving+companies&find_loc=Houston,+TX&page=1
```

Parsed via BeautifulSoup. For every `<a href="/profile/...">` on the page, we walk up to the nearest `card`/`listing` container and pull business name, phone, address, BBB rating, and accreditation flag. That produces a `ProfileStub`.

The card-container walk is intentionally conservative. It skips nodes whose class names contain `title`, `header`, or `link` (those are sub-containers, not the card root). If BBB changes their card markup, `tests/unit/agents/lead_generator/test_bbb_parser.py::TestParseSearchPage` fails loud — not a silent zero-leads in production. **That test is the canary.** Keep it.

Pagination: we walk `&page=2`, `&page=3`, … until one of:
- Server returns zero cards.
- Three consecutive pages have 100% duplicate `profile_url`s against what we've seen this run (city exhausted).
- `max_pages` (optional cap for testing) reached.

**Step 2 — Profile page.** One GET per business. The website URL lives here, not on the search page.

```
https://www.bbb.org/us/tx/houston/profile/moving-companies/westheimer-transfer-0915-27115
```

We extract the website URL two ways, in order:

1. **JSON-LD (`schema.org/LocalBusiness`)** — preferred. BBB embeds `<script type="application/ld+json">` with a `url` field pointing at the external site. Structured, stable.
2. **External-link scan** — fallback. `<a href="http...">` where the text contains "visit website" / "website" / "visit site" and the href doesn't point at `bbb.org`.

We also grab email (via `mailto:` link or visible text), BBB rating, accreditation, and years-in-business. If there's no website, the lead is skipped at the ingest stage (Scanner needs a URL to score).

### Why plain HTTP, not Playwright

BBB server-renders these pages. A realistic User-Agent (`BetterSiteBot/0.1 (+https://bettersite.co/bot)`) + browser-like `Accept`/`Referer` headers is enough — no Cloudflare challenge at our rate. Playwright would be 5-10× slower, require a headless-Chromium image on Railway, and provide no benefit here. If BBB ever starts gating the directory behind JS or CAPTCHAs, we revisit.

### Session reuse

One `httpx.AsyncClient` per flow run, HTTP/2 on, connection pool of 10 with 5 keep-alive. Cookies persist through pagination + profile fetches.

### Retries

`tenacity` with exponential backoff on `httpx.TransportError` and `BBBRateLimitError` (429). Default: 4 attempts, 2s → 30s.

### Error classes

| Class | Meaning | Policy |
|---|---|---|
| `BBBRateLimitError` | 429 with `Retry-After` respected | Retry (tenacity) |
| `BBBBlockedError` | 403 / CAPTCHA page | Single-city flow: halt. Batch flow: fail the city; second 403 aborts the batch. |
| `BBBNotFoundError` | 404 on a profile or search URL | Skip row, log, continue |
| `BBBParseError` | HTML structure unexpected | Skip row, log, continue |
| `BBBBatchAbortedError` | Raised by the batch flow after N 403s | Halt batch; operator intervenes |
| `BBBError` | Base class for all of the above | — |

No `except Exception`. Every exception is named.

### Rate limiting

Per-request jitter of 0.3-0.8s. No explicit global throttle beyond that; at ~1-1.5 req/sec from one IP, BBB is happy. Configurable via code if a run needs to be slower.

### Concurrency

**Sequential in v1.** Simpler; a full city takes ~2-3 min instead of ~30 seconds, and that's fine for how often we run this. `asyncio.Semaphore(N)` around profile fetches is the obvious next knob when we want it.

---

## Downstream pipeline

For every `RawLead` the source yields:

1. **Canonicalize URL** — `pipeline.utils.url.canonicalize_url()`. Lowercase, strip www, drop UTM/gclid/fbclid, sort query params, default-port strip, fragment drop. Raises `InvalidURLError` for junk.
2. **Extract canonical domain** — `canonicalize_domain()`. This is the dedup key.
3. **SSRF check** — `pipeline.utils.ssrf.assert_safe_url()`. Rejects non-http(s), RFC1918, link-local, IP literals resolving privately, `169.254.169.254` (cloud metadata), etc. Raises `UnsafeUrlError`.
4. **In-run dedup** — `seen_domains_this_run: set[str]`. Franchise chains and multi-listings collapse here so we don't re-hit the profile page for the same domain.
5. **UPSERT into `ops.leads`** — `INSERT ... ON CONFLICT (canonical_domain) DO UPDATE`. Idempotent by design: re-running the flow or a Prefect task retry is safe.
6. **Audit event** — one row in `ops.events` per UPSERT, `event_type = "lead_generator.upsert"`.
7. **Run summary** — one row per flow run with aggregate counts (`leads_seen`, `leads_inserted`, `leads_updated`, skips broken out by reason).

### UPSERT policy

On conflict (same `canonical_domain` already exists), we:
- Overwrite `business_name`, `vertical`, `website_url`, `source_metadata`.
- `COALESCE(excluded, existing)` for `phone`, `email`, `email_source`, `city`, `state` — prefer the existing non-null value rather than clobbering it with a second source that has less.
- Leave `status` untouched (so a `scanned` / `emailed` lead doesn't revert to `new`).

Proper deep-merge of `source_metadata` (preserving historical per-source detail when two sources claim the same domain) is a follow-up when FMCSA lands.

---

## Schema

`ops.leads` columns relevant to this agent:

| Column | Purpose |
|---|---|
| `canonical_domain` | UNIQUE dedup key. |
| `website_url` | Canonicalized form (stored, not the raw BBB link). |
| `state` | ISO 3166-2 subdivision; e.g. `TX`. Used for BBB URL construction, Scanner scoping, sales-agent copy. |
| `source` | String tag: `bbb` today, `fmcsa` / `google_maps` later. |
| `source_metadata` | JSONB. For BBB: `{"bbb_profile_url", "bbb_rating", "accredited", "address_raw", "years_in_business"}`. |
| `email_source` | `bbb` / `extracted` / `fallback_info_at` / null. Audit trail for deliverability debugging. |

---

## Running it

### Single city

**Prefect UI:** the `lead-generation` deployment takes `source`, `vertical`, `state`, `city`, `max_pages`.

**CLI:**

```
python -m scripts.enqueue_leads --state TX --city Houston --max-pages 1
```

### Batch across many cities

**Prefect UI:** the `lead-generation-batch` deployment takes:
- `source` — default `bbb`.
- `targets_csv` — path to a CSV with columns `vertical,state,city`. Default: `pipeline/targets/movers_us.csv`.
- `max_pages_per_city` — optional cap. Default `null` (walk until exhausted).
- `abort_on_repeated_block` — halt after this many BBB 403s in one run. Default `2`.

**CLI:**

```
python -m scripts.seed_cities                                       # default CSV
python -m scripts.seed_cities --targets pipeline/targets/foo.csv   # custom CSV
python -m scripts.seed_cities --max-pages-per-city 5               # testing
```

**Chunking guidance.** A city takes ~2-3 min. A 200-row CSV is ~10 hours and one Railway service restart forfeits everything since the crash point. For production runs, **split CSVs into ~50-row chunks** so a crash only costs one chunk. UPSERT makes re-running a chunk safe; chunking bounds the blast radius.

**Circuit breaker.** The batch flow tracks 403s across cities. One 403 fails that city and continues. A second 403 in the same run raises `BBBBatchAbortedError` and halts the flow: two in a row means our IP is flagged, and continuing just deepens the ban.

### Downstream cost

The Scanner is **pull-based** (`scan_sites` flow takes `limit`, default 50). Inserting a lead does **not** auto-trigger a scan. You control Scanner / Extractor / Sales-agent cost by choosing when to run `site-scan` and with what limit — running lead-gen wide is cheap.

---

## Adding a source

1. Create `pipeline/agents/lead_generator/sources/<yoursource>.py`:

    ```python
    class FMCSASource:
        name = "fmcsa"
        async def fetch(self, *, vertical, state, city, max_pages=None):
            async for lead in ...:
                yield RawLead(...)
    ```

2. Register in `pipeline/agents/lead_generator/sources/__init__.py`:

    ```python
    SOURCES: dict[str, type[LeadSource]] = {
        "bbb": BBBSource,
        "fmcsa": FMCSASource,   # ← new
    }
    ```

3. Run: `python -m scripts.enqueue_leads --source fmcsa --state TX --city Houston`

Nothing in the Prefect flow, the ingest pipeline, or the schema changes.

---

## Testing

All parser tests use fixture HTML in `tests/fixtures/bbb/` — no network. When BBB's markup changes in the wild, manually capture a fresh page, update the fixture, and adjust the test expectations.

```
pytest tests/unit/agents/lead_generator/
pytest tests/unit/utils/
pytest tests/unit/test_schema_invariants.py     # ensures the ops/app split is intact
```

Integration tests hitting the real DB belong in `tests/integration/` (not yet written for this agent — the end-to-end smoke test is running `enqueue_leads` against Houston manually).
