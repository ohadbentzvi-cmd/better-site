# TODOs

Durable backlog for things we deliberately deferred but must not forget. For
long-term roadmap items, see `PROGRESS.md` "TODOS (Post-POC)". This file is
for short-to-medium-term engineering debt captured during reviews.

---

## Open

### T6 — Configurable concurrency for the Extractor (`EXTRACTOR_CONCURRENCY`)
**Type:** performance — Information Extractor
**Captured:** 2026-04-26 during `/plan-eng-review` of Phase 3
**Priority:** P3 (only when 500-lead batch wall-clock becomes a complaint)

**Problem:** v1 runs sequentially, mirroring Scanner + Lead Generator v1. ~20s per
lead × 500 leads ≈ 3h per batch. Acceptable for an overnight run, painful for
mid-day reruns or debugging.

**Fix when it matters:** add `EXTRACTOR_CONCURRENCY: int = Field(default=1, ge=1, le=8)`
to `pipeline/config.py`, wrap the per-lead loop in `pipeline/agents/extractor/pipeline.py`
in an `asyncio.Semaphore`. Watch for: chromium memory (~200MB × N), R2 rate
limits, DB connection pool. Bump the default only after one full 500-lead batch
shows it's safe.

**Why this is open:** PROGRESS.md already deferred the same optimization for Lead
Generator. Same trigger here — first run measures actual wall-clock; only then
decide whether the optimization pays back the new failure surface.

**Revisit trigger:** after the first full POC batch, or when a single rerun blocks
debugging for >15min.

---

### T5 — R2 orphan cleanup for stale extraction assets
**Type:** ops hygiene — Information Extractor
**Captured:** 2026-04-26 during `/plan-eng-review` of Phase 3
**Priority:** P3 (defer until volume warrants)

**Problem:** when a lead is rejected, marked stale, or re-extracted with a different
image set, the old `extractions/{lead_id}/{logo,hero}.{ext}` R2 objects stay
behind. At POC scale (~500 leads × ~5MB peak) this is functionally zero
(~$0.04/mo at R2 rates). Becomes a real cost at v1.0+ scale.

**Fix when it matters:**
1. Periodic Prefect flow `extractions-r2-gc` that lists every key under
   `extractions/{lead_id}/` and deletes orphans where `lead_id` is not in
   `ops.leads` or `leads.status` is `rejected` / `unsubscribed`.
2. Or — soft-tier: add a presigned-URL accessor and lifecycle policy on R2
   that ages out objects older than X days where the lead is in a terminal state.

**Why this is open:** the Extractor's UPSERT-on-`lead_id` semantics overwrite
the same R2 keys on rerun, so there's no ongoing leak from extraction itself.
The leak is from leads exiting the funnel without their assets being cleared.
Not blocking the POC.

**Revisit trigger:** when total R2 storage exceeds 5GB or when we hit 5000 leads.

---

### T4 — Implement `vision_full` extraction strategy (v2)
**Type:** feature — Information Extractor v2
**Captured:** 2026-04-26 during `/plan-eng-review` of Phase 3
**Priority:** P1 (next thing after html_only is measured)

**Problem:** html_only ships in v1 as the deterministic baseline (no Claude calls,
no cost ceiling needed). It will miss things: logos that are inline SVG without
the word "logo", brand colors when the logo is on a complex background, hero
images on JS-rendered pages where the image only loads after scroll. Vision
catches these.

**Fix:**
1. Run html_only against ~50 real movers leads (pull from `ops.leads` after a
   week of Lead Generator runs). For each lead, eyeball the `ExtractionResult`
   and tag what's wrong (missing logo, wrong colors, weak hero). Quantify the
   gap rate.
2. If gap rate > 20%, implement `vision_full`:
   - Wire Anthropic SDK in `pipeline/agents/extractor/strategies/vision_full.py`
   - Prompt at `pipeline/prompts/extractor/vision_full.py`. Wrap all scraped
     content in `<UNTRUSTED_DATA>` per CLAUDE.md.
   - Add cost-ceiling enforcer: a per-batch counter that tracks
     `ExtractionResult.cost_usd` summed across leads; halt the flow when it
     exceeds `CLAUDE_COST_CEILING_PER_BATCH_USD`. Tracks the column added in
     v1's migration.
   - Manual comparison harness (NOT an eval suite — see CLAUDE.md): a
     side-by-side artifact for the same lead under both strategies, diffed in
     the Prefect UI.
   - Set `prompt_version` on every row written by vision_full so future prompt
     iterations are filterable.
3. After vision_full lands and is measured, decide on `hybrid` (vision-as-fallback)
   vs sticking with vision_full for everything. That's a separate trigger.

**Why this is open:** strategy decision deferred per CLAUDE.md "deferred elaborate
test infra until the Extractor strategy is picked." html_only ships first to
prove the schema and surface real gaps that warrant the Anthropic dependency.

**Revisit trigger:** after the v1 smoke check on ~10 leads + a follow-up batch
of ~50, when we have real evidence of html_only's gap rate.

---

### T3 — Add IP-based rate limit to `/admin/auth/verify`
**Type:** security hardening — Admin Review Console
**Captured:** 2026-04-16 during `/review` of the admin build
**Priority:** P2 (defer)

**Problem:** the current rate limiter keys on `username`, so an attacker can rotate usernames and force unlimited bcrypt-cost-12 hashes (~300 ms each). On Railway's shared CPU, a dozen concurrent attackers can flatline the api service.

**Why not blocking today:** the admin surface is an internal tool reachable by 2–3 analysts. Railway's edge blocks most automated abuse, and no public entrypoint exposes `/admin/auth/verify`. The pragmatic defense today is keeping the service token secret and the admin DNS unadvertised.

**Fix when it matters:**
1. Add an `ip` column to `ops.login_attempts` (nullable until backfilled).
2. Populate from `X-Forwarded-For` (trust only Railway's edge proxy) in `api/auth.py::authenticate_analyst`.
3. Check failures-per-IP in the last 15 min alongside failures-per-username. Trip 429 on whichever limit hits first.

**Revisit trigger:** before opening any public `/admin/*` entrypoint, or when the analyst pool grows beyond ~5 people (each failed login now costs more than one user's time).

---

### T2 — Tighten BBB rating / accreditation selectors against live markup
**Type:** follow-up to Lead Generator v1
**Captured:** 2026-04-15

Live run against BBB found 15 Houston movers successfully, but every one came back with `rating=None` and `accredited=False`. Selectors in `pipeline/agents/lead_generator/sources/bbb.py` (`_extract_rating`, `_extract_accredited`) are based on fixture HTML that mimics BBB's docs, not their live markup.

**Fix:** capture one real BBB search HTML into `tests/fixtures/bbb/search_live_sample.html`, inspect the actual class names / ARIA attributes BBB is using for rating badges, update selectors + fixture test. 20-minute job.

**Why not blocking:** rating is enrichment — name, website, phone, address land correctly. Scanner doesn't use rating yet. Sales-agent copy will want it later ("A+ rated mover in Houston").

---

### T1 — Grant default privileges when adding `web_role` / `app_role`
**Type:** follow-up to ops/app schema split
**Captured:** 2026-04-15 during `/plan-eng-review` of initial Alembic migration

When the Next.js service deploys and we split roles:

```sql
-- Role creation
CREATE ROLE web_role LOGIN PASSWORD '...';

-- Current grants
GRANT USAGE ON SCHEMA ops, app TO web_role;
GRANT SELECT ON ops.extractions TO web_role;
GRANT SELECT ON ops.suppression_list TO web_role;  -- /unsubscribe goes via FastAPI, but admin reads this
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA app TO web_role;
GRANT INSERT ON ops.events TO web_role;  -- Stripe webhook audit trail

-- Future-proof: make privileges auto-apply to tables created by LATER migrations
ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT SELECT, INSERT, UPDATE ON TABLES TO web_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA ops GRANT SELECT ON TABLES TO web_role;
```

The `ALTER DEFAULT PRIVILEGES` lines are the footgun. Without them, a migration
added six months from now will create a table `web_role` silently cannot read
or write, and the failure mode is an opaque 403 in the Next.js service.

**Why this is open:** No `web_role` exists yet; the worker service uses a single
`DATABASE_URL` for everything. Role split happens when the Next.js service gets
its own Railway service with its own DB credentials.

---

## Done

<!-- Move completed items here with date and PR reference. -->
