# BetterSite

**Automated cold-email outreach + website generation for small businesses.**

BetterSite is a web-studio product that prospects SMBs with underperforming websites, automatically generates a better replacement site, and sells it to them with a one-click $399 purchase. Low price, high volume, near-zero post-sale friction.

This repo contains the full system: the agent pipeline, the preview web app (planned), the internal review dashboard (planned), and the website templates (planned).

> **POC channel:** cold email only. A public self-serve channel (business owner enters their own URL) is deferred to post-POC.

---

## Status

**v0.2.0** — Foundations + Lead Generator v1 (BBB source) + Website Scanner v1 (PageSpeed + Playwright + HTTP) live in staging.

See [`PROGRESS.md`](./PROGRESS.md) for the roadmap and version history.

---

## Architecture at a Glance

**One Next.js app** will eventually serve the per-lead preview pages (`/preview/[slug]`), the unsubscribe flow, and the internal admin dashboard. Preview content is loaded from Postgres at request time — no per-lead deployments.

Behind it sits a **Python pipeline** with five sequential agents (four data + one sender), orchestrated by Prefect:

```
┌──────────────────────────────────────────────────────────┐
│                Next.js app (planned)                     │
│   /preview/[slug]  — personalized preview + checkout     │
│   /unsubscribe     — suppression-list opt-out            │
│   /admin/*         — internal review queue               │
└──────────────────────┬───────────────────────────────────┘
                       │ reads/writes
                       ▼
┌──────────────────────────────────────────────────────────┐
│                 Postgres (Railway)                        │
│   ops.*  (pipeline-owned)                                 │
│   app.*  (customer-facing)                                │
└──────────────────────▲───────────────────────────────────┘
                       │ writes
   ┌──────────┬────────┴────────┬──────────┬──────────────┐
   │          │                 │          │              │
┌─────────┐┌──────────┐┌─────────────┐┌─────────┐┌────────────────┐
│Lead Gen ││ Scanner  ││  Extractor  ││ Builder ││  Sales Agent   │
│ (v1 —   ││ (v1 —    ││   (next)    ││ (later) ││   (later)      │
│  BBB)   ││  PSI+PW) ││             ││         ││                │
└─────────┘└──────────┘└─────────────┘└─────────┘└────────────────┘
```

Today **Lead Generator** and **Scanner** are built. Extractor is next. The remaining agents + web app land phase-by-phase; tech stack for each is decided when the phase starts, not ahead of time.

---

## Database — schema split

One Postgres instance, two schemas:

- **`ops.*`** — pipeline-owned operational state. Today: `leads`, `scans`, `extractions`, `emails`, `suppression_list`, `events`.
- **`app.*`** — customer-facing surface. Today: `sites`, `payments`.

Every table sets a schema explicitly; a guard test fails the build if a new model forgets to. Cross-schema FKs target `ops.leads.id`. See [`docs/prefect.md`](./docs/prefect.md) for the two-DB topology (Prefect metadata vs app data).

---

## Lead Generator (shipped, v1)

Source-pluggable. Today only BBB is wired; FMCSA / Google Maps / etc. plug in as single-file additions under `pipeline/agents/lead_generator/sources/` without touching the flow, the ingest pipeline, or the schema.

Behavior — BBB source:
- Two-step fetch (search listings → profile page for the website URL).
- Plain `httpx.AsyncClient`, single session per flow run, HTTP/2 + keep-alive.
- CSS-selector parsing guarded by a fixture test — fails loud if BBB changes markup.
- JSON-LD preferred for the website URL, external-link scan as fallback.
- Explicit error hierarchy (`BBBRateLimitError`, `BBBBlockedError`, `BBBParseError`).
- Tenacity exponential backoff on transport errors; 429 respects `Retry-After`.
- Sequential for v1 — concurrency deferred.

Ingest pipeline (source-agnostic):
- Canonicalize URL → SSRF check → UPSERT on `canonical_domain` → per-lead audit event in `ops.events`.
- In-run dedup collapses franchise / duplicate listings.
- `ON CONFLICT` COALESCEs contact fields so a second source with less data can't clobber existing values.
- DB work off-loaded via `asyncio.to_thread` so the Prefect event loop isn't blocked.

Details + source-pluggable architecture: [`docs/lead_generator.md`](./docs/lead_generator.md).

---

## Website Scanner (shipped, v1)

Target-pluggable. Today two targets: `LeadTableTarget` (pulls unscanned leads from `ops.leads`) and `UrlListTarget` (explicit URLs, auto-matches to existing leads by canonical domain).

Scoring: Performance 45% + SEO 20% + AI-Readiness 20% + Security 15%. Partial scans (any unmeasurable dimension) produce `NULL` overall instead of a silently rescaled score.

Checks, per URL:
- **PageSpeed Insights API** (mobile + desktop, concurrent) — Google does the rendering; free tier covers 12k URL scans/day.
- **Single Playwright session** — desktop + mobile screenshots, plus DOM extraction (title, meta, OG tags, heading structure, image alt coverage, JSON-LD `@type`).
- **Parallel HTTP checks** — `robots.txt`, `llms.txt`, sitemap(s), five security headers.

Output: structured `Finding` list with SMB-ready language (e.g. _"Your site takes 3.9 seconds to load on mobile — slow enough that mobile visitors start bouncing."_) + per-dimension scores + raw metrics (LCP, CLS, TBT, page weight, …). Everything UPSERTed into `ops.scans` keyed on `lead_id`.

Details: [`docs/scanner.md`](./docs/scanner.md).

---

## Prefect

Two services on Railway:
1. **Prefect server** (Railway template) — UI + REST API, backed by its own Postgres.
2. **Worker service** (this repo's root `Dockerfile`) — runs `python -m pipeline.deploy`, which registers deployments and serves runs in-process.

No work pool, no `prefect worker` CLI. Scaling = more replicas of the worker service.

Details: [`docs/prefect.md`](./docs/prefect.md).

---

## Tech Stack (committed)

| Component | Tool | Why |
|---|---|---|
| Backend | Python 3.11, FastAPI (planned), SQLAlchemy 2.x, Alembic | Pipeline + future REST API |
| Orchestration | Prefect 3.x, self-hosted on Railway | Flow observability + retries |
| Database | Postgres (Railway) | Single source of truth |
| HTTP | httpx (async) | BBB scraper + future fetchers |
| Scraping / parsing | BeautifulSoup + lxml + tldextract | BBB + future site scrapers |
| Hosting | Railway | Prefect server + worker + app DB in one project |
| Git/CI | GitHub + GitHub Actions (planned) | Lint + tests + alembic check |

Other tooling (templates engine, object storage, AI for extraction, payments, email sending, monitoring, etc.) is selected at the phase that introduces it, not ahead of time.

---

## Repo Structure

```
bettersite/
├── README.md                ← you are here
├── PROGRESS.md              ← roadmap + version history
├── CLAUDE.md                ← coding rules for AI agents in this repo
├── TODOS.md                 ← deferred engineering tasks
├── .env.example             ← documents every env var the worker reads
│
├── pipeline/                ← Python — the agent pipeline
│   ├── agents/
│   │   └── lead_generator/  ← v1, BBB source
│   ├── flows/               ← Prefect flow entrypoints
│   ├── models/              ← SQLAlchemy models
│   ├── alembic/             ← DB migrations
│   ├── utils/               ← URL canonicalization, SSRF, etc.
│   ├── config.py            ← typed settings
│   ├── db.py                ← engine + session factory
│   ├── deploy.py            ← Prefect worker entrypoint
│   └── observability.py     ← structlog → Prefect logger bootstrap
│
├── docs/
│   ├── prefect.md           ← Prefect server + worker topology
│   └── lead_generator.md    ← Lead Generator walkthrough
│
├── scripts/
│   ├── enqueue_leads.py     ← CLI: trigger a one-off lead-generation run
│   └── seed_cities.py       ← CLI wrapper for the batch flow (CSV-driven)
│
├── tests/
│   ├── unit/
│   └── fixtures/            ← BBB HTML fixtures, more as new sources land
│
└── Dockerfile               ← Railway worker image
```

---

## Database Schema (shipped)

```
ops.leads
  id, business_name, vertical, website_url, canonical_domain UNIQUE,
  email, email_source, phone, city, state, country, source,
  source_metadata JSONB, status, created_at, updated_at

ops.scans             (table exists; agent not yet built)
ops.extractions       (table exists; agent not yet built)
ops.emails            (table exists; agent not yet built)
ops.suppression_list  (table exists; not wired yet)
ops.events            (used: lead_generator.upsert audit trail)

app.sites             (table exists; Builder not yet built)
app.payments          (table exists; Stripe integration deferred)
```

`leads.status` state machine:

```
new → scanned → extracted → built → review_pending →
  approved → emailed → followed_up → opened → clicked → purchased
                                         └→ rejected
                                         └→ bounced
                                         └→ unsubscribed
```

Only `new` is reached today. Each additional state lights up as its agent lands.

---

## Critical Implementation Constraints

These are enforced across the repo as invariants (see `CLAUDE.md` for the full list):

- **Idempotency.** Every agent's public write is `INSERT ... ON CONFLICT DO UPDATE`. Prefect retries must be safe.
- **Schema qualification.** Every table sets an explicit schema (`ops` or `app`). Guard test fails the build otherwise.
- **SSRF protection.** Every lead-supplied URL runs through `pipeline.utils.ssrf.assert_safe_url()` before any fetch.
- **No catch-all exceptions.** Every `except` names the exception class. Every failure path is explicit.
- **Typed everything.** Type hints on every signature. DTOs are pydantic / dataclass, never bare `dict`.

---

## Development Model

All development runs against a Railway staging project (Prefect server + app Postgres + worker service). No local Docker stack.

```bash
git clone git@github.com:ohadbentzvi-cmd/better-site.git
cd better-site
cp .env.example .env              # fill with the staging Railway URLs

# Run tests against fixtures (no network):
pytest

# Trigger a one-off lead-generation run from your laptop:
python -m scripts.enqueue_leads --state TX --city Houston --max-pages 1

# Deploy to Railway (the worker service auto-rebuilds):
git push
```

---

## POC Success Criteria

| Metric | Target |
|---|---|
| Verticals | 1 (movers) |
| Markets | US to start |
| Auto-qualified leads | 500+ |
| Pipeline failure rate | <5% leads stuck unrecoverably |
| Email bounce rate | <2% |
| Email reply rate | ≥3% |
| Preview click rate | ≥15% of opens |
| Conversions | 10+ paying customers |
| Cost per lead (all-in) | <$2 |

A single conversion is not the success criterion — unit economics across 500+ leads with a real conversion-rate measurement is.

---

## Out of Scope for POC

- Self-serve channel (`/scan?url=...`) — deferred; dedicated design later.
- Lawyers, cleaners, other verticals.
- UK market.
- Recurring billing / hosting subscription.
- DNS automation.
- Multi-language sites.
- A/B testing framework.
- Multi-tenant architecture.

Extended list in `PROGRESS.md`.

---

## Decisions Log — committed so far

| Decision | Choice | Rationale |
|---|---|---|
| Architecture | Approach A (cold-email only for POC); self-serve deferred | Self-serve is a full UX surface; don't split focus |
| Hosting model | One-time $399 sale | Keeps fulfillment cost near zero |
| POC scope | 500+ auto-qualified leads, 1 vertical, US | Statistically learnable, narrow wedge |
| Orchestration | Prefect 3.x on Railway, serve pattern (no work pool) | Operational simplicity |
| Database | Railway Postgres, `ops` / `app` schema split | Boundary-as-design without the ops cost of two DBs |
| Agent idempotency | UPSERT (`INSERT ... ON CONFLICT DO UPDATE`) | Safe Prefect retries without check-before-write |
| Preview hosting | Single Next.js app, dynamic routes (planned) | Avoid per-lead deploys |
| Dedup policy | Strict by `canonical_domain`, cross-schema-safe | Simplicity > flexibility |
| Lead Generator v1 source | BBB only; pluggable interface for future sources | Free, good coverage on movers, proven path |
| Email discovery | Scraped from lead's own site (not Hunter.io) | Better hit rate on SMBs, zero cost |
| UK market | Deferred | PECR/GDPR risk |

Tech-stack decisions for Phase 3+ (Extractor, Builder, Sales Agent, payments, object storage, email sending) will be made when those phases start.

---

## Contributing

Single-developer project. See `PROGRESS.md` for the current phase and next planned task.
