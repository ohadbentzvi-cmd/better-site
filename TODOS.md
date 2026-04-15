# TODOs

Durable backlog for things we deliberately deferred but must not forget. For
long-term roadmap items, see `PROGRESS.md` "TODOS (Post-POC)". This file is
for short-to-medium-term engineering debt captured during reviews.

---

## Open

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
