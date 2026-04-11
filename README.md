# BetterSite

**Automated cold-email outreach + website generation for small businesses.**

BetterSite is a web studio product that uses AI to (a) prospect SMBs with underperforming websites, (b) automatically generate a better replacement site, and (c) sell it to them via a one-click $399 purchase. It's a deliberate departure from the studio's high-touch service model: low price, high volume, near-zero post-sale friction.

This repo contains the entire system: the agent pipeline, the preview web app, the internal review dashboard, and the website templates.

> **POC channel:** cold email only. A public self-serve channel (where any business owner types their URL and sees a preview) is designed for but **deferred to post-POC** — it has enough scope, abuse-surface, and UX complexity that it deserves dedicated thinking rather than a bolt-on.

---

## Status

**Phase:** Pre-build. Repo just initialized. No code yet.
See [`PROGRESS.md`](./PROGRESS.md) for the full roadmap and version history.

---

## Architecture at a Glance

BetterSite is **one Next.js app** that serves the per-lead preview pages (`/preview/[slug]`), the unsubscribe flow, and the internal admin dashboard (`/admin`). All preview content is loaded from Postgres at request time — there are no per-lead deployments.

Behind the web app sits a Python backend with **five sequential agents** (four data + one sender), orchestrated by Prefect:

```
┌──────────────────────────────────────────────────────────┐
│              bettersite.co (Next.js)                     │
│                                                          │
│   /              ← minimal landing / brand page           │
│   /preview/[slug]← personalized preview + Stripe checkout │
│   /buy/success   ← post-payment confirmation              │
│   /unsubscribe   ← suppression list opt-out               │
│   /admin/*       ← internal review queue (HTTP auth)      │
└──────────────────────┬───────────────────────────────────┘
                       │ reads/writes
                       ▼
┌──────────────────────────────────────────────────────────┐
│                 Postgres (Railway)                       │
│   leads, scans, extractions, sites, emails,              │
│   payments, suppression_list, events                     │
└──────────────────────▲───────────────────────────────────┘
                       │ writes
   ┌──────────┬────────┴────────┬──────────┬──────────────┐
   │          │                 │          │              │
┌─────────┐┌──────────┐┌─────────────┐┌─────────┐┌────────────────┐
│Lead Gen ││ Scanner  ││  Extractor  ││ Builder ││  Sales Agent   │
│         ││          ││ (Claude     ││         ││ (1 cold + 1    │
│         ││          ││  vision)    ││         ││  follow-up)    │
└─────────┘└──────────┘└──────┬──────┘└─────────┘└───────┬────────┘
                              │                           │
                              ▼                           ▼
                      ┌──────────────┐          ┌──────────────────┐
                      │ Cloudflare R2│          │ Sales Agent      │
                      │ (assets)     │          │ interface:       │
                      └──────────────┘          │ stub in v0,      │
                                                │ impl decided in  │
                                                │ Phase 5 pre-     │
                                                │ flight. Always   │
                                                │ gated by         │
                                                │ ZeroBounce.      │
                                                └──────────────────┘
```

The pipeline is triggered exclusively by **one channel for POC**:
- **Cold-email channel** — leads enqueued from Google Maps + Hunter.io via a script

The code is structured so that a second channel (self-serve URL submission) can be added post-POC without rearchitecture. The `process_lead(lead_id)` Prefect flow doesn't care who enqueued the lead — it just processes it.

---

## The Five Agents

### 1. Lead Generator
Pulls SMBs from Google Maps Places API, finds emails via Hunter.io, deduplicates by canonical domain, writes qualified leads to Postgres. POC verticals: **movers only** (lawyers + cleaners deferred). POC countries: **US, CA, AU** (UK deferred for legal review).

### 2. Website Scanner
Scores the lead's existing site on speed (PageSpeed Insights), SEO basics, mobile responsiveness, security, GMB presence, and analytics. Below-threshold leads are filtered into the pipeline. Threshold tunable; starting at 60/100. Generates the personalized issues list used in the cold email.

### 3. Information Extractor
Renders the lead's site with Playwright, parses content with BeautifulSoup, and produces an `ExtractionResult` containing the business name, copy, images, logo, hero, brand colors, and social links. All extracted assets go to Cloudflare R2; structured content goes to the `extractions` table.

**Pluggable strategy architecture.** The Extractor is built around a common interface (`ExtractionStrategy`) with **four swappable implementations** that ship together in v0:

| Strategy | What it uses | Per-lead cost | Personalization ceiling |
|---|---|---|---|
| `html_only` | BeautifulSoup + `colorthief` + heuristics | $0 | Medium |
| `vision_full` | Claude Sonnet 4.6 vision for logo / hero / colors | $0.02-0.05 | Highest |
| `hybrid` | BS4 + colorthief first; Claude vision only as a fallback for low-confidence logo detection | $0.005-0.01 | High |
| `gmb_first` | Google Business Profile as primary source; Claude vision only for gaps | $0.005 | High |

The active strategy is selected at runtime via the `EXTRACTION_STRATEGY` env var. During the POC's Phase 3 build, the strategies are compared manually against a handful of real URLs — look at the outputs side-by-side, pick a winner. No automated comparison harness for POC; that's post-POC if we need it.

**Fallbacks.** If any strategy's website fetch fails entirely (site down, JS-only with no SSR, Cloudflare-blocked), the Extractor falls back to Google Business Profile data regardless of which strategy is active.

**Prompt injection hardening.** Any strategy that calls Claude wraps scraped content in `<UNTRUSTED_DATA>` tags and instructs the model to treat it as data, never as instructions.

### 4. Website Builder
Loads extraction data, maps it into the vertical template's content schema, runs a **light Claude polish** on tagline + headline only (with a guardrail prompt to avoid AI slop), and writes a row to the `sites` table. The site is immediately accessible at `bettersite.co/preview/[slug]` with a 48-hour expiry. **No per-lead deploys.**

### 5. Sales Agent
Verifies the email address with **ZeroBounce** as a hard gate, checks the suppression list, then hands the `(lead, email_html, subject)` to a pluggable `SalesAgentBackend` interface. The email contains an embedded screenshot of the new preview (deliverability test required pre-launch) and a link to the preview page. **One follow-up email** is sent at T+24h if the prospect hasn't opened, replied, or bought. After two touches, the lead is closed.

> **v0 backend strategy: decoupled and deferred.** The Sales Agent ships in v0 with two backend implementations — `NullSalesAgentBackend` (writes to `emails` table, logs the send; no real send) and `ConsoleSalesAgentBackend` (prints the email). The actual sending backend (Smartlead / Instantly / raw SMTP / Postmark) is picked in Phase 5 pre-flight and implemented as a third `SalesAgentBackend` subclass. All pipeline + admin + review code treats the interface as opaque — no code path needs to change when the real backend lands. The sales agent's full sequence and copy are also deliberately under-specified for v0 — the focus during the build is on the technical pipeline. Sequence design and copywriting are revisited before launch.

---

## The Preview Page (the product)

The preview page is where the prospect actually decides whether to buy. Five things make it different from "a link in an email":

1. **Before/after slider** at top-of-fold — drag to compare their old site against the new one.
2. **Mobile-first layout** — most SMB owners read email on phones.
3. **Embedded Stripe Checkout** — Stripe Elements modal on the same page, no redirect.
4. **Sticky "Buy this site for $399" bar** at the bottom of the viewport.
5. **"Share with your business partner" button** — generates a shareable link that bypasses the original recipient gate.

The page is the highest-leverage UI in the whole product.

---

## Tech Stack

| Component | Tool | Why |
|---|---|---|
| Web app | Next.js (App Router) | Preview pages + admin |
| Backend | Python 3.11 + FastAPI | Pipeline + REST API |
| Orchestration | Prefect (Railway template) | Flow observability + retries |
| Database | Postgres (Railway) | Single source of truth |
| ORM | SQLAlchemy + Alembic | Migrations from day 1 |
| Object storage | Cloudflare R2 | S3-compatible, free egress, no migration debt |
| Scraping | Playwright + BeautifulSoup | Renders JS, parses HTML |
| AI | Claude Sonnet 4.6 (vision + text) | Extraction + light copy polish |
| Lead source | Google Maps Places API | Structured business data |
| Email finder | Hunter.io | Reasonable cost/coverage at POC scale |
| Email verifier | ZeroBounce | Hard gate before send |
| Email send | `SalesAgentBackend` interface; impl TBD in Phase 5 | Decoupled — v0 ships stub implementations only |
| Page speed scoring | PageSpeed Insights API | Free, reliable |
| Payments | Stripe (Elements + webhooks) | Standard |
| Hosting | Railway | All services in one project |
| DNS / CDN | Cloudflare | Free, gives DDoS + SSL termination |
| Error monitoring | Sentry | Standard |

---

## Repo Structure

```
bettersite/
├── README.md                ← you are here
├── PROGRESS.md              ← roadmap, completed work, version history
├── DESIGN.md                ← (TBD) design system + UI principles
├── CLAUDE.md                ← (TBD) instructions for Claude Code agents
├── .env.example             ← (TBD) all env vars documented, no secrets
│
├── pipeline/                ← Python — agent flows
│   ├── flows/
│   │   ├── lead_generator.py
│   │   ├── website_scanner.py
│   │   ├── website_extractor.py
│   │   └── website_builder.py
│   ├── agents/              ← per-agent business logic
│   ├── tasks/               ← Prefect tasks (small reusable units)
│   ├── models/              ← SQLAlchemy models
│   ├── prompts/             ← Claude prompts (versioned)
│   ├── utils/               ← shared helpers (URL canon, slug gen, etc.)
│   ├── alembic/             ← DB migrations
│   └── requirements.txt
│
├── api/                     ← FastAPI — backend for the Next.js app
│   ├── main.py
│   ├── routes/
│   │   ├── preview.py       ← /preview/[slug] data
│   │   ├── stripe.py        ← /webhooks/stripe
│   │   ├── unsubscribe.py
│   │   └── admin.py         ← review queue endpoints
│   └── requirements.txt
│
├── web/                     ← Next.js — preview + admin app
│   ├── app/
│   │   ├── page.tsx         ← minimal landing / brand page
│   │   ├── preview/[slug]/  ← preview page (slider + checkout)
│   │   ├── unsubscribe/
│   │   └── admin/
│   ├── components/
│   ├── lib/
│   └── package.json
│
├── templates/               ← website templates (per vertical)
│   └── movers/              ← v0 template — content.json driven
│       ├── components/
│       └── content.schema.json
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/            ← fixture HTML sites + screenshots for evals
│
├── docs/
│   ├── deliverability.md    ← warmup playbook + seed test
│   ├── runbook.md           ← what to do when things break
│   └── designs/             ← (TBD) feature design docs
│
├── scripts/
│   ├── enqueue_leads.py     ← cold-email channel: feed leads to pipeline
│   └── seed_test_email.py   ← deliverability seed test
│
# No docker-compose. Development happens against a Railway staging project — see PROGRESS.md.
```

---

## Database Schema (v0)

```sql
leads
  id, business_name, vertical, website_url, canonical_domain (unique),
  email, phone, city, country, source, status, created_at, updated_at

scans
  id, lead_id, score, pass_fail, issues_json,
  pagespeed_mobile, pagespeed_desktop, has_ssl, has_mobile,
  has_analytics, screenshot_r2_key, created_at

extractions
  id, lead_id, content_json, images_json, brand_colors,
  vision_model_version, scraped_at

sites
  id, lead_id, slug (unique, nanoid), preview_url,
  status, expires_at, created_at

emails
  id, lead_id, subject, body, sequence_step (1=initial, 2=followup),
  sent_at, opened_at, clicked_at, status, smtp_inbox_used

payments  ← NEW vs architect's plan
  id, lead_id, stripe_payment_intent_id, amount_cents,
  status (succeeded/refunded/disputed), raw_webhook,
  created_at, updated_at

suppression_list  ← NEW vs architect's plan
  id, email, domain, reason (unsubscribe/bounce/complaint/manual),
  created_at

events  ← NEW vs architect's plan
  id, lead_id, event_type, payload (jsonb), created_at
```

`leads.status` state machine:
```
new → scanned → extracted → built → review_pending →
  approved → emailed → followed_up → opened → clicked → purchased
                                         └→ rejected
                                         └→ bounced
                                         └→ unsubscribed
```

---

## Critical Implementation Constraints

These came out of the plan review. They are not optional.

### Security
1. **Preview slugs must be unguessable** — use `nanoid(12)` or `cuid2`. Never sequential IDs.
2. **SSRF protection in the pipeline URL fetchers** — the Lead Generator, Scanner, and Extractor all fetch lead-supplied URLs. Before any HTTP request or Playwright navigation, resolve the URL and block RFC1918, link-local, `169.254.169.254` (cloud metadata), `file://`, and non-http(s) schemes. Prevents a malicious lead URL from being used as an internal-network pivot.
3. **Prompt injection hardening** — wrap all scraped content in `<UNTRUSTED_DATA>` tags in Claude prompts; instruct the model to treat it as data.
4. **Sanitize extracted HTML** — isomorphic-dompurify (server-side) before rendering inside the preview page.
5. **Stripe webhook signature verification** — required on `/webhooks/stripe`.
6. **Admin dashboard** — HTTP basic auth, credentials in Railway env vars, rotated on a calendar reminder.

### Deliverability
1. **Start warming 2-3 sender domains in week 1 of build, not week 8.** This is the longest-lead-time item in the project. Sending domains need ~14 days of warmup before first cold email.
2. **ZeroBounce verification is a hard gate** — never send to an address marked invalid, risky, or catch-all.
3. **Pre-launch deliverability seed test** — send to 10-20 inboxes you control (Gmail, Outlook, Yahoo, Apple Mail) and verify all land in inbox before sending the first real batch.
4. **The image-in-email approach (cherry-pick #1) needs deliverability testing** before launch — image+link emails can trip spam filters.
5. **Suppression list is checked before every send.** No exceptions.

### Cost control
1. **Per-batch Claude cost ceiling** — halt batch and alert if Claude vision spend exceeds e.g. $20 per 200-lead batch.
2. **Cost dashboard from day 1** — track Claude $/day, Hunter $/day, ZeroBounce $/day.

### Data integrity
1. **Builder.publish must be transactional** — wrap site row insert in a transaction with retry+rollback. Lost-lead-on-DB-error is a critical gap in the architect's plan.
2. **Strict dedupe by canonical domain** — one domain → one lead → one preview. After 48h expiry, no auto-rebuild.

---

## Development Model

**No local Docker stack.** Development runs against a dedicated Railway staging project (separate from `bettersite-poc` production). Every push to a feature branch deploys to staging automatically via Railway's Git integration. The staging environment has its own Postgres, its own Prefect server, and its own Cloudflare R2 bucket — no shared state with production.

For unit tests and prompt iteration that shouldn't hit real APIs, the Extractor prompts run against committed HTML fixtures in `tests/fixtures/` with **mocked Claude responses** (recorded from an earlier real call). The real Claude API is only hit in the eval suite (run manually before any prompt change).

```bash
# Quick start (placeholder)
git clone https://github.com/ohadbentzvi-cmd/better-site.git
cd better-site
cp .env.example .env  # pointed at Railway staging
# Run tests against fixtures:
cd pipeline && pytest
# Deploy to staging:
git push origin feature/my-branch  # Railway picks it up
```

---

## POC Success Criteria

| Metric | Target |
|---|---|
| Verticals | 1 (movers) |
| Markets | US, CA, AU |
| Auto-qualified leads | 500+ |
| Pipeline failure rate | <5% leads stuck unrecoverably |
| Email bounce rate | <2% |
| Email reply rate | ≥3% |
| Preview click rate | ≥15% of opens |
| Conversions | 10+ paying customers |
| Cost per lead (all-in) | <$2 |
| Time-to-first-customer | ≤14 days from first send |

A single conversion is no longer the success criterion — that was statistically meaningless. POC is "did the unit economics work out across 500+ leads with a real conversion-rate measurement."

---

## Out of Scope for POC

- **Self-serve channel (`/scan?url=...`)** — deferred to post-POC for dedicated design. Whole surface needs its own UX, abuse modeling, rate limiting, captcha, SEO indexing strategy, and analytics. Cold email only for v0.
- Lawyers vertical
- Cleaners vertical
- UK market
- Recurring billing / hosting fee
- DNS automation (manual guide for v0)
- Multi-language sites
- Loom-style walkthrough video generation
- Customizable colors widget on the preview
- Reply auto-triage
- A/B testing framework
- SEO indexing of preview pages
- Any kind of multi-tenant architecture (no other studios using BetterSite as a tool)

See [`PROGRESS.md`](./PROGRESS.md) for the full deferred-work list.

---

## Decisions Log

The full record of every architectural / scope decision made during the planning review lives in `~/.gstack/projects/ohadbentzvi-cmd-better-site/ceo-plans/2026-04-11-bettersite-poc.md` (local) and is summarized in `PROGRESS.md`. Major decisions:

| Decision | Choice | Rationale |
|---|---|---|
| Architecture | Approach A for POC — single Next.js app, preview routes only, cold-email only channel. Approach C (self-serve) deferred to post-POC. | Self-serve is a full UX surface that deserves dedicated design; bolting it onto POC would split focus. |
| Hosting model | Static one-time $399 sale (no recurring) | Keeps fulfillment cost near zero |
| POC scope | 500+ auto-qualified leads, 1 vertical, 3 markets | Statistically learnable; narrow wedge |
| Orchestration | Prefect via Railway template | Operational cost is trivial when managed |
| Agent idempotency | UPSERT-based (`INSERT ... ON CONFLICT DO UPDATE`) | Safe Prefect retries without check-before-write boilerplate |
| Object storage | Cloudflare R2 from day 1 | Avoid MinIO → R2 migration debt |
| Email finder | Hunter.io for v0 | Acceptable for scale; revisit if accuracy poor |
| Email verifier | ZeroBounce, hard gate | Non-negotiable for deliverability |
| Email sending backend | Pluggable `SalesAgentBackend` interface, real impl deferred to Phase 5 pre-flight | Decouples pipeline build from sending-infra choice |
| Preview hosting | Single Next.js app, dynamic routes | Avoid per-lead Vercel deploys |
| Dedup policy | Strict by canonical domain, 48h TTL | Simplicity > flexibility |
| UK market | Deferred (legal review) | PECR/GDPR risk |

---

## Contributing

This is a single-developer project for now. See `PROGRESS.md` for the current build phase and the next planned task.
