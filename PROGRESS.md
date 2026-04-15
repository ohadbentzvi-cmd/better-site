# BetterSite — Progress

Running log of where the project is, what's done, what's next, and version history. README is the spec; this is the timeline.

---

## Current Version

**v0.1.0** — Phase 1 (Foundations) complete + Lead Generator v1 (BBB source) shipped to staging.

---

## Current Phase

**Phase 0 — Planning** ✅ DONE
**Phase 1 — Foundations** ✅ DONE
**Phase 2 — Lead Generator** ✅ v1 SHIPPED (BBB only; improvements open)
**Phase 2.5 — Website Scanner** ⏳ NEXT

---

## Roadmap

Tech stack for phases later than the current + next is intentionally left undefined. We decide what each phase uses when we start it — not ahead of time.

### Phase 0 — Planning ✅ DONE

- [x] Repo connected to GitHub
- [x] Architecture locked (Approach A for POC — cold-email only)
- [x] POC scope locked (500+ auto-qualified movers leads, US)
- [x] `README.md`, `PROGRESS.md`, `CLAUDE.md` written

### Phase 1 — Foundations ✅ DONE

- [x] Railway project with Prefect server (Railway template) + Prefect metadata Postgres
- [x] Separate Railway Postgres for app data
- [x] Worker Railway service — root `Dockerfile` running `python -m pipeline.deploy`
- [x] `pipeline/config.py` — phase-gated typed settings; only `DATABASE_URL` + `PREFECT_API_URL` required
- [x] `pipeline/db.py` — cached engine + session factory
- [x] Alembic wiring with two-schema (`ops`, `app`) support
- [x] Initial migration: every v0 table + schemas + enum types
- [x] Schema invariant tests — every table has a schema, every FK is schema-qualified
- [x] `pipeline/observability.py` — structlog routed through Prefect's logger
- [x] `docs/prefect.md` — topology + deploy/update cycle documented

### Phase 2 — Lead Generator ✅ v1 SHIPPED

**v1 delivered (movers / US, BBB only):**

- [x] `LeadSource` Protocol + `RawLead` pydantic model
- [x] `BBBSource` — two-step fetch (search → profile), CSS-selector parsing, tenacity retries, explicit error hierarchy, fixture-based parser tests
- [x] Source-agnostic ingest pipeline — canonicalize URL → SSRF check → UPSERT → per-lead audit event
- [x] `ops.leads` gains `state`, `source_metadata` JSONB, `email_source`
- [x] In-run dedup by `canonical_domain`
- [x] `pipeline/flows/lead_generator.py` — Prefect flow with markdown run-summary artifact + `get_run_logger` output
- [x] `scripts/enqueue_leads.py` — CLI for one-off runs
- [x] `scripts/seed_cities.py` — hardcoded seed list of US metros
- [x] `docs/lead_generator.md` — dev-team walkthrough + add-a-source guide
- [x] Smoke-tested live: Houston + Austin + San Diego leads ingested cleanly, UPSERT idempotent across reruns

**Open in Phase 2 (blocking or worth doing before Phase 2.5):**
- [ ] Tighten BBB rating / accreditation selectors against live markup (TODOS: T2)
- [ ] Parameterless scheduled flow that iterates seed cities and skips recently-scraped combos (plan approved, not yet built)

**Deferred to later — intentionally not building now:**
- FMCSA source. Revisit when BBB coverage is measured and found insufficient.
- Google Maps fallback.
- Concurrent profile-page fetches.
- Deep merge of `source_metadata` for multi-source overlap.
- Multi-country (CA, AU).

### Phase 2.5 — Website Scanner ⏳ NEXT

Takes a `lead_id`, fetches the lead's site, scores it, writes `ops.scans`, flips `leads.status`. Exact scoring design + any external APIs will be decided at the start of the phase.

What we know going in:
- Idempotent UPSERT keyed on `lead_id`.
- SSRF-safe fetches via `pipeline.utils.ssrf.assert_safe_url()`.
- Explicit failure modes, no catch-all.
- Structured log events per scan step.

### Phase 3+ (not yet specified)

- **Information Extractor** — turn a lead's website into a structured `ExtractionResult` the Builder can use.
- **Website Builder** — generate a preview site per lead.
- **Preview Web Surface** — Next.js preview page, unsubscribe, payment confirmation.
- **Admin dashboard + Sales Agent** — review queue, cold-email sending.
- **End-to-end batch** — first ~100 live sends, then scale to 500.

Design + tech stack for each of these lands at phase start.

---

## Done

| Date | Item | Version |
|---|---|---|
| 2026-04-11 | Repo scaffold, planning docs, initial models (no runtime code yet) | v0.0.2 |
| 2026-04-14 | Prefect worker wired via Dockerfile + `pipeline.deploy` (serve pattern) | — |
| 2026-04-15 | Ops/app schema split; real lead-generation UPSERT; phase-gated config | — |
| 2026-04-15 | Lead Generator v1 (BBB pluggable source) merged to main | — |
| 2026-04-15 | Deployment params fix (flow signature drift after v1 rewrite) | — |
| 2026-04-15 | Observability: structlog → Prefect logs; run-summary markdown artifact | v0.1.0 |

---

## Critical Implementation Constraints

Enforced across the repo. See `CLAUDE.md` for the full coding-rules list.

### Security
- Preview slugs will use `nanoid(12)` (never sequential IDs) — enforced when the Builder lands.
- SSRF check before every fetch against a lead-supplied URL. Wired in Lead Generator.
- Prompt-injection hardening (`<UNTRUSTED_DATA>` wrapper) — enforced when the first Claude-calling agent lands.
- HTML sanitization on any scraped content rendered in the preview — enforced when the preview lands.

### Data integrity
- Every public write is idempotent (`INSERT ... ON CONFLICT DO UPDATE`).
- Every table has an explicit schema. Guard test fails the build otherwise.
- Dedup by canonical domain, cross-schema-safe.

### Cost control
- Per-batch cost ceilings and a cost dashboard land when the first paid external service is wired.

---

## Failure Modes Registry

Extend with each new codepath. Catch-all `except Exception` is forbidden.

### Lead Generator (Phase 2)

| Codepath | Failure | Rescue |
|---|---|---|
| BBB search/profile GET | 429 | Tenacity backoff; respect `Retry-After` |
| BBB search/profile GET | 403 / CAPTCHA | `BBBBlockedError`; halt batch, alert |
| Card parse | Unexpected HTML | `BBBParseError`; skip row, log, continue |
| Fixture test | BBB changed markup | Parser test fails at build time — the canary |
| Canonicalize URL | Malformed / non-http(s) | `InvalidURLError`; skip lead |
| SSRF check | RFC1918 / link-local / metadata IP | `UnsafeUrlError`; skip lead |
| UPSERT | Unique violation from concurrent insert | `ON CONFLICT` is atomic; UPSERT is idempotent |

### Scanner, Extractor, Builder, Sales Agent

To be written when each agent lands.

---

## Out of Scope for POC

- **Self-serve channel (`/scan?url=...`).** Deferred to post-POC with dedicated UX / abuse modeling.
- UK market (legal review required).
- Lawyers + cleaners verticals.
- Recurring billing / hosting subscription.
- DNS automation.
- Multi-language sites.
- Loom-style walkthrough videos.
- Customizable colors widget on the preview.
- SEO indexing of preview pages.
- Multi-tenant architecture.
- Reply auto-triage.
- A/B testing framework.
- Customer support / ticketing.
- Refund-flow UI.

---

## TODOS (Post-POC)

Roughly priority-ordered. Each becomes a real plan if/when we decide to build it.

1. **Self-serve channel** — design and ship `/scan?url=...` with full UX, abuse modeling, SEO strategy. Depends on the POC pipeline being proven end-to-end.
2. **UK / GDPR legal review** — re-enable UK market.
3. **Additional verticals** — lawyers, cleaners, etc.
4. **Additional lead sources** — FMCSA (movers-specific), Google Maps (paid fallback).
5. **Sales-agent sequence v2** — full sequence + copy work beyond the T+24h follow-up.
6. **Reply auto-triage** — classify inbound replies automatically.
7. **A/B testing framework** — subject / body / CTA variants.
8. **Multi-vertical template engine** — once 5+ verticals exist.
9. **Recurring billing model** — if hosting ever becomes a subscription.

---

## Open Questions

Resolved-ish but worth revisiting with real data.

| # | Question | Current answer | Revisit when |
|---|---|---|---|
| 1 | BBB coverage on movers in mid-size US metros | "Looks good" | After 500 real leads; measure pass rate by city |
| 2 | Conversion-rate hypothesis | "5-10% on narrow wedge" | After first real batch |

---

## Version History

### v0.0.1 — 2026-04-11
Empty project connected to GitHub. Plan review done. `README` + `PROGRESS` written.

### v0.0.2 — 2026-04-11
Eng review; architecture revised from self-serve to cold-email-only for POC; Sales Agent interface pattern locked; UPSERT idempotency locked.

### v0.1.0 — 2026-04-15
Foundations done + Lead Generator v1 shipped.

- Railway: Prefect server + separate app Postgres + worker service on root `Dockerfile`.
- Config phase-gated — worker boots with only `DATABASE_URL` + `PREFECT_API_URL`.
- Schema split: `ops.*` pipeline-owned, `app.*` customer-facing. Guard tests enforce placement.
- Lead Generator v1: pluggable `LeadSource` interface + `BBBSource` implementation + source-agnostic ingest pipeline. Hunter.io explicitly removed; email discovery happens from the lead's own site later. New columns `state`, `source_metadata`, `email_source`.
- Prefect observability: structlog routed through the Prefect logger; flow runs emit a markdown run-summary artifact.

**Next version (v0.2.0):** Website Scanner (Phase 2.5) landing in `ops.scans` with idempotent UPSERT and the first pass of the scoring function.

---

## Versioning Convention

- **v0.x.0** — POC build phases. Each major phase = minor version bump.
- **v0.x.y** — bug fixes, small additions within a phase.
- **v1.0.0** — POC ships. First real batch of 500 emails sent.
- **v1.x.0** — post-POC iteration.
- **v2.0.0** — self-serve product publicly launched.
