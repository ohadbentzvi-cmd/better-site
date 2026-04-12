# Runbook

What to do when things break. Populated incrementally during the build —
this is the placeholder.

## Template

```
### <Failure name>

**Symptom:**
**Detection:**
**Immediate action:**
**Root cause investigation:**
**Long-term fix:**
```

## Known failure modes

See `PROGRESS.md` → "Failure Modes Registry" for the canonical list of
critical gaps to fix during build. Each will get a runbook entry here as
its rescue path lands in code.

## Useful commands

```bash
# Tail staging API logs
railway logs --service api --environment staging

# Re-run a single Prefect flow manually
cd pipeline && python -c "from flows.process_lead import process_lead; process_lead('<lead-uuid>')"

# Inspect a specific lead's full event history
psql "$DATABASE_URL" -c "SELECT event_type, payload, created_at FROM events WHERE lead_id = '<uuid>' ORDER BY created_at;"
```
