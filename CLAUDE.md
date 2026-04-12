# CLAUDE.md — BetterSite

Conventions for Claude Code (and any AI coding agent) working in this repo.

> **Read `README.md` for the spec and `PROGRESS.md` for the roadmap before starting any new task.** The CEO plan decision log is at `~/.gstack/projects/ohadbentzvi-cmd-better-site/ceo-plans/2026-04-11-bettersite-poc.md`.

---

## Architecture summary

- **One Next.js app** (`web/`) for preview pages + admin + unsubscribe.
- **One FastAPI service** (`api/`) serving JSON to the Next.js app + Stripe webhooks.
- **One Python pipeline** (`pipeline/`) with four data agents + one sales agent, orchestrated by Prefect.
- **Shared Postgres** (Railway) with tables: `leads`, `scans`, `extractions`, `sites`, `emails`, `payments`, `suppression_list`, `events`.
- **Cloudflare R2** for assets.

Development runs against a Railway **staging** project (no docker-compose, no local stack). See `README.md` "Development Model".

---

## Non-negotiable coding rules

### Idempotency

**Every agent's public entrypoint must be idempotent.** Prefect retries failed tasks — if your code writes half its output and then crashes, the retry must be safe. Use `INSERT ... ON CONFLICT DO UPDATE` for all writes. Never check-then-write without a transaction.

```python
# GOOD
stmt = insert(Scan).values(...).on_conflict_do_update(
    index_elements=["lead_id"],
    set_={...}
)
session.execute(stmt)
```

### No catch-all error handling

```python
# FORBIDDEN
try:
    ...
except Exception:
    pass

# REQUIRED
try:
    ...
except PageSpeedTimeoutError as e:
    logger.warning("pagespeed_timeout", lead_id=lead.id, exc_info=e)
    raise  # or handle with a specific fallback
```

Every exception class must be explicit. If you're catching something you didn't name, name it first. The Failure Modes Registry in `PROGRESS.md` lists every known error class and its rescue path — extend it when you add new ones.

### Typed everything

- Every function signature has type hints.
- DTOs are `pydantic.BaseModel` or `dataclasses.dataclass(frozen=True)` — never bare `dict`.
- SQLAlchemy models use `Mapped[T]` style annotations (SQLA 2.x).

### Prompt injection hardening

Any prompt that includes lead-supplied content (scraped HTML, business names, etc.) MUST wrap that content in `<UNTRUSTED_DATA>...</UNTRUSTED_DATA>` tags and tell the model it's data, not instructions. See `pipeline/prompts/extractor/` for the canonical pattern.

### SSRF protection

Any code path that fetches a lead-supplied URL (Lead Generator, Scanner, Extractor) must call `pipeline.utils.ssrf.assert_safe_url(url)` BEFORE making the request. This helper blocks RFC1918, link-local, `169.254.169.254`, and non-http(s) schemes.

### No sequential / guessable IDs in URLs

Preview slugs and any other user-facing identifiers use `nanoid(12)` (see `pipeline.utils.slug.generate_slug()`). Never expose database primary keys in URLs.

### HTML sanitization on render

Any scraped content rendered inside the preview page goes through `isomorphic-dompurify` server-side before React sees it. The template layer trusts its inputs — sanitization is the Builder's responsibility.

---

## Testing posture

**Current phase: simple unit tests only.**

Per user direction (2026-04-11), elaborate test infrastructure (recorded API responses, eval suites, comparison harnesses, prompt-change gates) is **explicitly deferred** until the Extractor strategy is picked. For now:

- Happy-path unit tests for each agent
- Idempotency tests where UPSERT logic lives
- One end-to-end test through the pipeline against fixtures (added in Phase 6)
- One E2E test for the preview → checkout flow (Stripe test mode)

Don't add recorded Claude responses, eval runners, or comparison tools without checking in first.

### Test layout

```
tests/
├── unit/              # Per-module unit tests (mirrors pipeline/ structure)
├── integration/       # Cross-module tests hitting a real staging DB
├── e2e/               # Playwright E2E against the running app
└── fixtures/          # Shared test fixtures (HTML, JSON, SQL)
```

### Naming

- Pytest files: `test_<module>.py`
- Classes: `Test<Thing>`
- Functions: `test_<behavior>_<scenario>` e.g. `test_canonicalize_strips_trailing_slash`

---

## Prompt/LLM change patterns

Any file under these paths is considered a prompt change and requires extra care:

- `pipeline/prompts/**/*.py`
- `pipeline/prompts/**/*.txt`
- `pipeline/prompts/**/*.md`
- `pipeline/agents/extractor/strategies/vision_full.py`
- `pipeline/agents/extractor/strategies/hybrid.py` (the vision-fallback portion)
- `pipeline/agents/website_builder.py` (the copy-polish call)

**Before changing any of these:** manually test against a handful of fixture websites and eyeball the output. The eval suite and comparison harness are deferred — so this check is your only safety net. Note your findings in the PR description.

---

## Directory ownership

- `pipeline/` — Python, owned by the pipeline. No Next.js code here.
- `api/` — Python, FastAPI. Thin wrappers around the pipeline's data models.
- `web/` — TypeScript, Next.js. No Python here. No business logic — just rendering and thin fetch calls to `api/`.
- `templates/` — Next.js templates per vertical. Content is injected via props from `web/app/preview/[slug]/page.tsx`.
- `scripts/` — one-off Python utilities run by humans (lead enqueue, seed tests).
- `docs/` — prose documentation.
- `tests/` — all tests, mirrors source structure.

Crossing these boundaries (e.g. importing from `web/` into `pipeline/`) is forbidden.

---

## Database changes

All schema changes go through Alembic:

```bash
cd pipeline
alembic revision --autogenerate -m "description"
alembic upgrade head  # applies to $DATABASE_URL in .env
```

Before merging:
- Review the generated migration — autogenerate is not perfect.
- Migrations must be backward-compatible with old code still running (for zero-downtime deploys).
- Add indexes for any new hot-path query.

---

## Commit & PR conventions

- One logical change per PR. No "kitchen sink" branches.
- Commit messages describe the *why*, not the *what*. The diff shows what.
- Every commit should leave the repo in a state that passes lint + tests.
- Version bumps happen at the end of a phase (see `PROGRESS.md` versioning section).

---

## What not to do without checking

Flag these in the PR description and wait for review:

- Adding a new external service (SaaS, API, library with paid tier)
- Changing an interface (`ExtractionStrategy`, `SalesAgentBackend`)
- Touching a prompt file (see "Prompt/LLM change patterns" above)
- Schema migrations that aren't backward-compatible
- Anything that changes the POC scope as documented in `PROGRESS.md`

---

## Quick reference

| Need | File |
|---|---|
| Product spec | `README.md` |
| Roadmap + done log | `PROGRESS.md` |
| CEO-level decisions | `~/.gstack/projects/ohadbentzvi-cmd-better-site/ceo-plans/2026-04-11-bettersite-poc.md` |
| Test plan for /qa | `~/.gstack/projects/ohadbentzvi-cmd-better-site/ohadbentzvi-main-eng-review-test-plan-20260411.md` |
| Env vars contract | `.env.example` |
| Coding rules | this file |
