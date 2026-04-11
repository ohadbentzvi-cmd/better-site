# BetterSite — Progress

This file is the running log of where the project is, what's been done, what's planned next, and the version history. Every major commit bumps the version. The README is the spec; this file is the timeline.

---

## Current Version

**v0.0.2** — Repo initialized + planning complete + eng review complete. No code yet.

---

## Current Phase

**Phase 0 — Planning** ✅ DONE
**Phase 1 — Foundations** ⏳ NEXT

---

## Roadmap (Build Order)

The build order has been re-sequenced from the architect's original 10-week plan to reflect:
- **Approach A** for POC — cold-email channel only. Self-serve deferred to post-POC.
- The 2-week email-domain warm-up dependency starts immediately
- The accepted scope expansions (8 of original 9; one — self-serve-specific — dropped with the channel)

### Phase 0 — Planning ✅ DONE
- [x] Connect repo to GitHub
- [x] Run `/plan-ceo-review` on the architecture plan
- [x] Lock architectural approach (C)
- [x] Lock POC scope (500+ auto-qualified leads, narrow wedge)
- [x] Resolve UK / GDPR question (deferred)
- [x] Cherry-pick accepted scope expansions (9 items)
- [x] Document decisions in README + PROGRESS

### Phase 1 — Foundations (Week 1)
**Parallel tracks. Track A is engineering. Track B is the long-lead-time deliverability work.**

**Track A — Engineering setup**
- [ ] Railway project: `bettersite-poc` (production)
- [ ] Railway project: `bettersite-staging` (all development happens here; auto-deploys from feature branches)
- [ ] Provision Postgres on Railway (one per project)
- [ ] Provision Prefect via Railway template
- [ ] Provision Cloudflare R2 bucket
- [ ] Set up Cloudflare DNS for `bettersite.co` (or chosen domain)
- [ ] Create `pipeline/`, `api/`, `web/`, `templates/`, `tests/` directory structure
- [ ] Initialize Python project (FastAPI + SQLAlchemy + Alembic + Prefect client)
- [ ] Initialize Next.js app (App Router + Tailwind + shadcn/ui)
- [ ] Write `.env.example` documenting every env var
- [ ] Write initial Alembic migration: `leads`, `scans`, `extractions`, `sites`, `emails`, `payments`, `suppression_list`, `events`
- [ ] CI: GitHub Actions for lint + tests + alembic check
- [ ] Sentry integration on both Python + Next.js
- [ ] Cost-tracking helper module (Claude $/day, Hunter $/day, ZeroBounce $/day → events table)
- [ ] Write `CLAUDE.md` with project conventions

**Track B — Deliverability long-lead work** ⚠️ START IN WEEK 1
- [ ] Choose 2-3 sender domains (e.g. `betterstudio.co`, `bettersites.co`, `bettersitepro.com`)
- [ ] Buy domains, configure SPF / DKIM / DMARC properly
- [ ] Set up SMTP inboxes per domain (2-3 inboxes per domain → 4-9 inboxes total)
- [ ] Begin warm-up sequence (Mailwarm / Warmup Inbox / Instantly warm-up)
- [ ] Document warm-up curve in `docs/deliverability.md`
- [ ] Write seed-test script: send identical email to inboxes you control across Gmail/Outlook/Yahoo/Apple Mail

### Phase 2 — Lead Generator + Scanner (Week 2)
- [ ] Lead Generator flow: Google Maps Places API → canonicalize → Hunter.io → dedupe → DB insert
- [ ] URL canonicalization helper (handles `www.`, trailing slash, scheme, redirects)
- [ ] Tests: 3 fixture lead inputs, 2 dedup edge cases
- [ ] Website Scanner flow: PageSpeed Insights + HTML scrape → score → pass/fail → issues_json
- [ ] Score weighting tuned to reject ~50-60% of raw leads
- [ ] Tests: 5 fixture sites with known scores
- [ ] **Goal:** 500 leads in DB by end of week, ~250 passing the scanner filter

### Phase 3 — Extractor + Builder (Week 3)

**Extractor — pluggable strategy architecture.** The Extractor is the highest-leverage quality surface and the "right" approach isn't knowable in advance without real comparison data. Build it as an orchestrator + swappable strategy interface. All strategies ship in v0. The active strategy is picked via `EXTRACTION_STRATEGY` env var. A comparison harness lets you run every strategy against the same real URL and eyeball the results side-by-side.

- [ ] `ExtractionStrategy` Protocol / abstract base class
  - Interface: `extract(url: str, html: str, screenshot_path: str) -> ExtractionResult`
  - Registry pattern: strategies self-register by name
- [ ] Shared prerequisites (used by all strategies):
  - [ ] Playwright page renderer → HTML + full-page screenshot + viewport screenshot
  - [ ] BeautifulSoup text extraction helpers (name, phone, address, social, copy)
  - [ ] `colorthief` wrapper for deterministic color extraction from screenshot
  - [ ] Google Places API helper (reuse from Lead Generator) for GMB lookup
  - [ ] Image download + R2 upload helper (MIME + size validation, SSRF-safe)
  - [ ] URL canonicalizer (shared with Lead Generator)
- [ ] **Strategy: `html_only`** — pure BS4 + colorthief + heuristics. Logo = first image in `<header>`/`<nav>` or image with "logo" in filename. Hero = largest image in first viewport. Colors = colorthief top 3. No Claude calls. Deterministic, free.
- [ ] **Strategy: `vision_full`** — Claude Sonnet 4.6 vision for logo, hero, brand colors. Text still via BS4. One prompt with `<UNTRUSTED_DATA>` wrapper. Highest personalization ceiling, highest cost (~$0.02-0.05/lead), non-deterministic output.
- [ ] **Strategy: `hybrid`** — BS4 + colorthief for everything first; Claude vision ONLY called as a fallback when the HTML heuristic for logo returns low-confidence (e.g. no `<header>` image found, no "logo" filename match). Cost ~$0.005-0.01/lead. Should hit vision on ~20-30% of leads.
- [ ] **Strategy: `gmb_first`** — Google Places API is the primary source (logo, photos, hours, phone, address). Website scraping is fallback. Claude vision only for brand colors when GMB has no color data. Cost ~$0.005/lead.
- [ ] GMB fallback path when any strategy's website fetch fails entirely (site is down, JS-only with no SSR, Cloudflare-blocked)
- [ ] Per-batch Claude cost ceiling enforcement ($20 / 200-lead batch starting value)
- [ ] `<UNTRUSTED_DATA>` prompt injection hardening on every strategy that calls Claude

**Extractor tests:** simple unit tests per strategy — basic happy-path assertions against a couple of fixture HTML files. Deeper test infrastructure (recorded Claude responses, eval suites, comparison harness) is explicitly deferred until after we've actually picked a direction on which strategies work. Premature optimization to build it before then.

**Strategy comparison — manual for now.** When the strategies are working, we'll run a small number of them against real URLs by hand and compare outputs together. No harness required for POC.

**Movers vertical template (first version):**
- [ ] `templates/movers/` Next.js component
- [ ] `content.schema.json` defining required + optional fields (matches ExtractionResult shape)
- [ ] Mobile-first layout
- [ ] Sticky "Buy this site for $399" CTA bar
- [ ] Graceful degradation when extraction data is partial (missing logo → text wordmark; missing hero → stock; missing colors → template defaults)

**Website Builder:**
- [ ] Extraction JSON → template content schema mapper
- [ ] Slug generation: `nanoid(12)`
- [ ] `Builder.publish` wrapped in transaction with retry + rollback
- [ ] UPSERT-based idempotency on all writes
- [ ] Tests: build 10 leads end-to-end, all 10 produce valid preview pages with graceful handling of missing fields

### Phase 4 — Preview Web Surface (Week 4)
- [ ] Next.js: minimal landing page (`/`) — brand + "built by BetterSite" only, not a product page
- [ ] Next.js: `/preview/[slug]` dynamic route
  - [ ] Loads preview content from Postgres
  - [ ] Middleware: 404 if `expires_at < now()`
  - [ ] **Before/after slider** at top-of-fold (uses scanner's screenshot of old site + new preview render)
  - [ ] **Embedded Stripe Elements checkout**
  - [ ] **Sticky buy bar**
  - [ ] **Share-with-partner button** (cherry-pick #9) — generates a second access token for the same preview
  - [ ] HTML sanitization on all extracted content (isomorphic-dompurify server-side)
- [ ] Next.js: `/unsubscribe` writes to `suppression_list`
- [ ] Next.js: `/buy/success` post-payment page
- [ ] Stripe webhook handler → `payments` table → updates lead status
- [ ] Stripe webhook signature verification
- [ ] Stripe idempotency keys
- [ ] Tests: E2E for email link → preview → checkout → success (Stripe test mode)

### Phase 5 — Internal Dashboard + Sales Agent interface (Week 5)
- [ ] Next.js: `/admin` (basic HTTP auth)
- [ ] Admin: leads view (table, filters, status counts)
- [ ] Admin: review queue
  - [ ] Iframe of preview site
  - [ ] Scan results bullets
  - [ ] Approve / Reject / Edit buttons
  - [ ] Idempotent approve action
- [ ] Admin: cost dashboard (Claude / Hunter / ZeroBounce $/day)
- [ ] Admin: pipeline funnel dashboard (created → scanned → passed → built → sent → opened → clicked → bought)
- [ ] **Pre-flight decision: pick the real `SalesAgentBackend` implementation** (Smartlead / Instantly / raw SMTP / Postmark). Cannot proceed to Phase 6 without this.
- [ ] Sales Agent flow:
  - [ ] `SalesAgentBackend` interface (`send(lead, email_html, subject) -> SendResult`)
  - [ ] `NullSalesAgentBackend` — writes emails row, no real send
  - [ ] `ConsoleSalesAgentBackend` — prints email + screenshot details
  - [ ] Real `SalesAgentBackend` subclass — depends on pre-flight decision
  - [ ] ZeroBounce verify gate (before interface call)
  - [ ] Suppression list check (before interface call)
  - [ ] Cold email v1 template (subject + body) — MJML → HTML
  - [ ] Embedded screenshot of preview in HTML body (hosted on R2 with long-lived signed URL)
  - [ ] **Follow-up email at T+24h** (cherry-pick #6)
  - [ ] Open / click tracking pixels
- [ ] Tests: send → bounce → suppression flow (using NullBackend)

### Phase 6 — End-to-End Test + First Real Batch (Week 6)
- [ ] **Pre-launch deliverability seed test** to 10-20 inboxes you control. ALL must land in inbox.
- [ ] **Pre-launch image-in-email deliverability test** (cherry-pick #1 caveat)
- [ ] End-to-end test: 50 fixture leads through full pipeline
- [ ] Fix all critical failures
- [ ] Tune scanner threshold based on actual lead quality
- [ ] **First real batch:** 100 emails to verified leads
- [ ] Monitor bounce rate, complaint rate, open rate, click rate hourly
- [ ] Adjust based on results

### Phase 7 — Scale to 500 (Week 7)
- [ ] Resolve any deliverability issues from week 6
- [ ] Send remaining 400 emails over 5-7 days, distributed across inboxes
- [ ] Track conversion rate
- [ ] Document findings → go/no-go memo

---

## Done

| Date | Item | Notes |
|---|---|---|
| 2026-04-11 | Repo initialized | `git init`, remote added, `main` branch set up |
| 2026-04-11 | CEO review run | `/plan-ceo-review` in selective expansion mode. 9 cherry-picks accepted. 5 strategic challenges raised + resolved. |
| 2026-04-11 | README + PROGRESS written | Initial documentation reflecting all planning decisions |
| 2026-04-11 | Eng review run | `/plan-eng-review`. Architecture revised: reverted from Approach C to Approach A (cold-email only) for POC; self-serve channel deferred to post-POC. Sales Agent interface pattern locked. Agent idempotency locked to UPSERT. DB indexes specified. |

---

## Critical Implementation Constraints

These came out of the plan review and must be enforced during build. They are reproduced here as a checklist.

### Security (must-fix)
- [ ] Preview slugs use `nanoid(12)` or `cuid2` — never sequential IDs
- [ ] SSRF protection **in the pipeline URL fetchers** (Lead Gen, Scanner, Extractor). Block RFC1918, link-local, metadata IPs, non-http(s) schemes before any Playwright navigation or HTTP fetch against a lead-supplied URL.
- [ ] Prompt injection hardening: `<UNTRUSTED_DATA>` wrapper in Claude prompts
- [ ] HTML sanitization (isomorphic-dompurify server-side) on all extracted content rendered in preview
- [ ] Stripe webhook signature verification

### Deliverability (must-fix)
- [ ] Sender domains warm-up started in **Week 1**, not Week 8
- [ ] ZeroBounce hard gate before any send
- [ ] Pre-launch seed test to 10-20 inboxes you control
- [ ] Image-in-email deliverability test before launch
- [ ] Suppression list check on every send

### Cost control (must-fix)
- [ ] Per-batch Claude cost ceiling
- [ ] Cost dashboard from day 1

### Data integrity (must-fix)
- [ ] `Builder.publish` transactional with retry + rollback
- [ ] Strict canonical-domain dedup, 48h TTL, no auto-rebuild

---

## Failure Modes Registry

From the plan review's error & rescue mapping. Every method that can fail is named, has a specific exception class, and has a rescue path. Catch-all `except Exception` is forbidden.

The full registry lives in the plan review notes; the critical gaps to fix during build are:

| # | Codepath | Failure | Fix |
|---|---|---|---|
| 1 | `Builder.publish` | DB write fails → lead lost | Wrap in transaction, retry once, alert |
| 2 | `Extractor.claude_vision` | No global cost ceiling | Per-batch dollar cap with halt + alert ($20 / 200-lead starting value) |
| 3 | Pipeline URL fetchers (Lead Gen, Scanner, Extractor) | No SSRF protection | Block RFC1918, link-local, metadata IPs, non-http(s) schemes before any navigation |
| 4 | Preview slug generation | Sequential / guessable | nanoid(12) or cuid2 |
| 5 | All agents | Prefect retries cause duplicate writes | UPSERT-based idempotency (`INSERT ... ON CONFLICT DO UPDATE`) on every write |
| 6 | `Extractor` prompt | No prompt injection hardening | `<UNTRUSTED_DATA>` wrapper |
| 7 | Preview render | No HTML sanitization | isomorphic-dompurify server-side |
| 8 | Sender domains | Warm-up not started early | Track B starts Week 1 in parallel with engineering |
| 9 | `/webhooks/stripe` | Webhook signature unverified → spoofable | Use Stripe SDK signature verification on every webhook request |
| 10 | `emails` table | No DB indexes | Indexes on all hot query columns — see the initial Alembic migration |

---

## Out of Scope for POC

These are NOT being built. They're tracked here so we don't lose them.

- **Self-serve channel (`/scan?url=...` public form)** — deferred to post-POC for dedicated design. Requires its own UX, rate limiting, SSRF protection on a public endpoint, Turnstile captcha, abuse modeling, SEO indexing strategy. Cold-email channel only for v0.
- UK market (legal review required)
- Lawyers vertical template
- Cleaners vertical template
- DNS automation (manual guide for v0)
- Recurring billing / hosting subscription
- Multi-language sites (English only)
- Loom-style walkthrough video generation
- Customizable colors widget on preview
- "Your domain available?" check on preview
- Reply auto-triage (manual triage for v0)
- A/B testing framework (manual variants for v0)
- SEO indexing of preview pages (robots.txt: `Disallow: /preview/`)
- Multi-tenant architecture
- Customer support / ticketing system
- Refund flow UI

---

## TODOS (Post-POC)

Captured during plan review. Ordered roughly by priority.

1. **Self-serve channel (high priority)** — design and ship `/scan?url=...` as a public surface with full UX work, abuse modeling (SSRF + rate limit + Turnstile), SEO indexing strategy, and analytics. This is the dream-state architecture (Approach C from CEO review). Depends on: the POC pipeline working end-to-end, so the backend is proven before we point a public surface at it. Blocked by: POC go/no-go decision.
2. **UK / GDPR legal review** — re-enable UK market with proper compliance
3. **Lawyers vertical template** — v2 of templates engine
4. **Cleaners vertical template**
5. **Sales agent v2: full sequence design + copy refinement** — under-specified in v0 by design
6. **DNS automation feasibility research** — what % of SMBs use API-accessible registrars?
7. **Loom-style walkthrough video generation** — high impact, high cost
8. **SEO indexing strategy** — `bettersite.co/preview/[business-name-slug]` as a real SEO play (depends on self-serve channel existing)
9. **Customer support / ticketing system** — Intercom? Plain? Email forwarding?
10. **Refund flow + dispute handling UI** — admin tool for Stripe disputes
11. **A/B testing framework** — subject line variants, body variants, CTA variants
12. **Reply auto-triage** — Claude-powered classification of replies (interested / question / unsubscribe)
13. **Multi-vertical template engine** — replace hard-coded templates with a CMS-style system once we have 5+ verticals
14. **Recurring billing model** — decide if hosting becomes a subscription
15. **Multi-tenant model** — could BetterSite be sold as a tool to other studios?

---

## Open Questions

These are resolved-ish but worth revisiting based on actual data.

| # | Question | Current Answer | Revisit When |
|---|---|---|---|
| 1 | Hunter.io accuracy on movers in US | "Probably acceptable" | After first 500 leads, measure invalid % |
| 2 | Movers template aesthetic | "Mobile-first, no AI slop" | After `/plan-design-review` on the template |
| 3 | Per-batch Claude cost ceiling | "$20/batch placeholder" | After first batch, calibrate |
| 4 | SMTP inbox rotation strategy | "Round-robin, halt inbox at 2% bounce" | After first deliverability seed test |
| 5 | Conversion rate hypothesis | "5-10% on narrow wedge" | After first real batch |
| 6 | Whether self-serve users actually return after expiry | Unknown | After 100 self-serve scans |

---

## Version History

### v0.0.1 — 2026-04-11
**Type:** Planning + repo initialization
**Summary:** Empty project connected to GitHub. Full plan review completed. README + PROGRESS written incorporating all decisions.

**Decisions made:**
- Architecture: Approach C (self-serve first, cold email second) — replaces architect's per-lead Vercel deploy plan with a single Next.js app + dynamic routes
- POC scope: 500+ auto-qualified leads in movers vertical, US/CA/AU markets
- UK market: deferred until legal review
- Orchestration: Prefect via Railway template
- Object storage: Cloudflare R2 from day 1 (skip MinIO migration debt)
- Email verification: ZeroBounce as a hard gate
- Email finder: Hunter.io for v0
- Dedup: strict by canonical domain, 48h TTL, no auto-rebuild
- Hosting model: one-time $399 sale, no recurring billing for v0

**Scope additions accepted (cherry-picks):**
1. Embedded preview screenshot in cold email (with deliverability test caveat)
2. Before/after slider on preview page
3. Embedded Stripe Elements checkout
4. ZeroBounce email verification gate
5. Suppression list table from day 1
6. One follow-up email at T+24h (timing locked; full sequence/copy is "sales agent v2", deferred)
7. Events / audit log table
8. Payments table for Stripe webhooks
9. Share-with-partner button on preview

**Critical gaps surfaced (must-fix during build):** 9 items — see "Critical Implementation Constraints" above.

**Files added:**
- `README.md`
- `PROGRESS.md`

**Next version:** v0.1.0 — Phase 1 (Foundations) complete. Railway services live, DB schema migrated, both Track A (engineering) and Track B (deliverability warm-up) underway.

### v0.0.2 — 2026-04-11
**Type:** Planning (eng review)
**Summary:** Eng review surfaced implementation-spec gaps. Architecture revised to Approach A for POC — self-serve channel deferred to post-POC as a dedicated workstream (too much UX/abuse/SEO surface to bolt on). Sales Agent backend pattern locked: pluggable interface with null/console impls in v0, real backend picked in Phase 5 pre-flight. Agent idempotency locked to UPSERT-based. Database indexes specified. Additional critical gaps added to registry (Stripe webhook signing, idempotency, DB indexes).

**Architecture changes:**
- Reverted from Approach C → Approach A for POC (cold-email channel only)
- `/scan` route, Turnstile, rate limiting, and public SSRF protection removed from scope
- SSRF protection moved to pipeline URL fetchers (where it's still needed — scraping lead-supplied URLs)
- Sales Agent flow now describes a pluggable `SalesAgentBackend` interface + v0 stub implementations (`NullSalesAgentBackend`, `ConsoleSalesAgentBackend`). Real backend decision deferred to Phase 5 pre-flight.
- All agent DB writes specified as UPSERT for Prefect retry safety

**Cherry-picks retained (8 of 9):** screenshots in email, before/after slider, Stripe Elements, ZeroBounce gate, suppression list, T+24h follow-up, events table, payments table, share-with-partner button. All still in scope — none were self-serve-specific.

**Scope reductions:**
- Self-serve `/scan` channel → TODOS post-POC (top priority)
- Public rate limiting / Turnstile → deferred with channel
- Phase 4 renamed "Public Web Surface" → "Preview Web Surface"

**Files changed:**
- `README.md` — architecture diagram, routes list, tech stack, security constraints, decisions log
- `PROGRESS.md` — Phase 4/5 restructured, critical gaps updated, TODOS reordered with self-serve as #1, out-of-scope expanded

---

## Versioning Convention

- **v0.x.0** — POC build phases. Each major phase = minor version bump.
- **v0.x.y** — Bug fixes, small additions within a phase.
- **v1.0.0** — POC ships. First real batch of 500 emails sent.
- **v1.x.0** — Post-POC iteration: scaling, lawyers vertical, cleaners vertical, etc.
- **v2.0.0** — Self-serve product is publicly launched as a standalone offering.
