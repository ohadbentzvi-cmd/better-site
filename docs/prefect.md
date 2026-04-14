# Prefect Setup

How Prefect is wired up in BetterSite. Three moving parts, all on Railway, all deployed from this repo.

## Topology

```
┌─────────────────────────────┐         ┌─────────────────────────────┐
│  Prefect Server (Railway)   │◄────────┤  Worker / Serve (Railway)   │
│  prefect template / image   │  HTTP   │  Dockerfile (repo root)     │
│  :4200  UI + REST API       │         │  runs `python -m pipeline.  │
│                             │         │         deploy`             │
└──────────────┬──────────────┘         └──────────────┬──────────────┘
               │                                       │
               │ asyncpg / psycopg                     │ SQLAlchemy
               ▼                                       ▼
      ┌──────────────────┐                   ┌──────────────────────┐
      │  Postgres        │                   │  App Postgres        │
      │  (Prefect state) │                   │  leads, scans, ...   │
      │   Railway        │                   │   Railway            │
      └──────────────────┘                   └──────────────────────┘
```

Two distinct databases:
1. **Prefect metadata DB** — stores flow runs, schedules, logs, deployment state. Used only by the Prefect server.
2. **App DB** — `leads`, `scans`, `extractions`, `sites`, `emails`, `payments`, `suppression_list`, `events`. Used only by flow code.

There is **no local worker and no Prefect work-pool**. The "worker" is `prefect.serve()` running inside a long-lived Railway service.

## The three services

### 1. Prefect Server

- Provisioned via the Railway Prefect template.
- Exposes the UI and REST API on `:4200`.
- Points at its own dedicated Postgres service via `PREFECT_API_DATABASE_CONNECTION_URL`.
- Only Railway env to care about here: the DB URL and any standard `PREFECT_*` tuning knobs.

### 2. Worker (serve process) — root `Dockerfile` + `pipeline/deploy.py`

- Image installs `pipeline/requirements.txt` and copies the repo.
- `CMD ["python", "-m", "pipeline.deploy"]`.
- `pipeline/deploy.py` imports each flow, calls `flow.to_deployment(...)`, then `prefect.serve(...)` which:
  - Registers/updates the deployments on the server (idempotent upsert by name).
  - Blocks and polls the server for scheduled or manually triggered runs.
  - Executes flow code **in-process** on this Railway service.
- Points at the server via `PREFECT_API_URL=https://<prefect-server>.up.railway.app/api`.
- Reaches the app DB via `DATABASE_URL` (read by `pipeline/config.py`).

Because runs execute in-process, scaling = running more replicas of this service. There is no separate work-pool/worker layer.

### 3. App Postgres

Not Prefect-owned. Flows connect through the SQLAlchemy engine configured in `pipeline/config.py`.

## Registered deployments

Defined in `pipeline/deploy.py`:

| Deployment | Flow | Schedule | Purpose |
|---|---|---|---|
| `lead-generation` | `generate_leads` | on-demand | Phase 1 demo; real Google Maps + Hunter.io implementation lands in Phase 2 |

Adding a deployment = add another `to_deployment(...)` + include it in the `serve(...)` call, then redeploy the Railway worker service. The `serve()` call is the source of truth; anything not listed there gets no runs.

## Deploy / update cycle

1. Edit flow code under `pipeline/flows/` or register a new deployment in `pipeline/deploy.py`.
2. Commit + push. Railway rebuilds the worker service from the root `Dockerfile`.
3. On boot, `pipeline.deploy:main()` re-registers each deployment and starts serving.
4. Removed deployments stay as orphan rows in the server DB — prune manually via a small script or the Prefect UI when they accumulate.

## Required environment variables

**Prefect server service**
- `PREFECT_API_DATABASE_CONNECTION_URL` — Prefect metadata Postgres (asyncpg URL).
- Any standard `PREFECT_*` tuning knobs.

**Worker service**
- `PREFECT_API_URL` — e.g. `https://<prefect-server>.up.railway.app/api`.
- `DATABASE_URL` — app Postgres (read by `pipeline/config.py`).
- Any flow-specific secrets (`ANTHROPIC_API_KEY`, `HUNTER_API_KEY`, `ZEROBOUNCE_API_KEY`, `GOOGLE_MAPS_API_KEY`, Stripe keys, R2 creds, …). See `.env.example`.

## Triggering runs

- **Scheduled**: attach a cron to a deployment in `pipeline/deploy.py` via `to_deployment(..., cron="0 1 * * *")`. The server fires on schedule; the serving worker picks it up on its next poll.
- **Manual**: Prefect UI → deployment → *Run*, or `prefect deployment run '<flow>/<deployment>'` with `PREFECT_API_URL` pointed at the Railway server.
- **Programmatic**: `prefect.client.orchestration.get_client()`.

## Gotchas

- **No local worker** — running `python -m pipeline.deploy` locally while the Railway worker is up will cause both processes to race for the same runs. Don't. For local iteration call flow functions directly (`python -m pipeline.flows.lead_generator`) or point a one-off local `serve()` at a *staging* Prefect server only.
- **Redeploying replaces the process** — any in-flight run on the old container is killed by Railway's rolling restart. Prefer to deploy outside known scheduled windows.
- **Connection pool sizing** — with >1 worker replica, multiply SQLAlchemy pool sizes against the app DB's connection limit.
- **Idempotency** — per `CLAUDE.md`, every flow's DB writes must be UPSERT-based. Prefect retries failed tasks, so partial writes followed by a retry must be safe.
