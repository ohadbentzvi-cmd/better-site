"""Website Extractor flow.

Pulls leads from ``ops.leads`` whose ``status`` is ``new`` or ``scanned``
and have no row in ``ops.extractions``, then runs the configured strategy
per lead. Successful runs UPSERT the extraction and advance lead status
``new``/``scanned`` → ``extracted``. The transition is gated by the
current status so a rerun never regresses a lead that has already moved
further down the funnel (e.g. ``built``, ``approved``).

Two input modes:

- Leads-table mode: ``lead_ids=None`` (default). Pulls the next ``limit``
  pending leads in created_at order.
- Explicit mode: ``lead_ids=[...]``. Re-runs extraction for those leads
  regardless of current status — useful for QA / strategy comparison.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from prefect import flow, get_run_logger
from prefect.artifacts import create_markdown_artifact
from sqlalchemy import select, update
from sqlalchemy.orm import aliased

from pipeline.agents.extractor.pipeline import (
    ERROR_CATEGORY_SSRF,
    ERROR_CATEGORY_STRATEGY,
    ERROR_CATEGORY_UNREACHABLE,
    ExtractorOutcome,
    extract_lead,
)
from pipeline.db import session_scope
from pipeline.models import Extraction, Lead
from pipeline.models.lead import LeadStatus
from pipeline.observability import configure as configure_logging

log = structlog.get_logger(__name__)


@flow(name="website-extractor")
async def extract_websites(
    lead_ids: list[uuid.UUID] | None = None,
    limit: int | None = 50,
) -> dict[str, Any]:
    """Run the Information Extractor against a batch of leads."""
    configure_logging()
    run_log = get_run_logger()
    started_at = datetime.now(tz=timezone.utc)

    pending = await asyncio.to_thread(_load_pending_leads, lead_ids, limit)
    mode = "explicit" if lead_ids else "leads_table"
    run_log.info(
        "website-extractor starting | mode=%s count=%d", mode, len(pending),
    )

    outcomes: list[ExtractorOutcome] = []
    for lead_id, url in pending:
        outcome = await extract_lead(lead_id, url)
        outcomes.append(outcome)
        if outcome.succeeded:
            await asyncio.to_thread(_advance_status_to_extracted, lead_id)

    finished_at = datetime.now(tz=timezone.utc)
    summary = _summarize(outcomes)

    await create_markdown_artifact(
        key="extractor-run-summary",
        markdown=_run_summary_markdown(
            mode=mode,
            limit=limit,
            started_at=started_at,
            finished_at=finished_at,
            outcomes=outcomes,
            summary=summary,
        ),
        description=f"Extractor run — {summary['targets_seen']} leads",
    )

    run_log.info(
        "website-extractor complete | seen=%d ok=%d ssrf=%d unreachable=%d strat=%d cost=$%.4f",
        summary["targets_seen"],
        summary["succeeded"],
        summary["skipped_ssrf"],
        summary["skipped_unreachable"],
        summary["strategy_failed"],
        summary["total_cost_usd"],
    )
    return summary


# ── DB helpers ──────────────────────────────────────────────────────────────


def _load_pending_leads(
    lead_ids: list[uuid.UUID] | None,
    limit: int | None,
) -> list[tuple[uuid.UUID, str]]:
    extraction_alias = aliased(Extraction)
    stmt = (
        select(Lead.id, Lead.website_url)
        .outerjoin(extraction_alias, extraction_alias.lead_id == Lead.id)
        .where(Lead.website_url.isnot(None))
    )
    if lead_ids:
        stmt = stmt.where(Lead.id.in_(lead_ids))
    else:
        stmt = (
            stmt.where(extraction_alias.id.is_(None))
            .where(Lead.status.in_([LeadStatus.new, LeadStatus.scanned]))
            .order_by(Lead.created_at.asc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
    with session_scope() as session:
        rows = session.execute(stmt).all()
    return [(r.id, r.website_url) for r in rows if r.website_url]


def _advance_status_to_extracted(lead_id: uuid.UUID) -> None:
    """``new``/``scanned`` → ``extracted``. Other states are left untouched."""
    stmt = (
        update(Lead)
        .where(Lead.id == lead_id)
        .where(Lead.status.in_([LeadStatus.new, LeadStatus.scanned]))
        .values(status=LeadStatus.extracted)
    )
    with session_scope() as session:
        session.execute(stmt)
        session.commit()


# ── Summary + artifact ──────────────────────────────────────────────────────


def _summarize(outcomes: list[ExtractorOutcome]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "targets_seen": len(outcomes),
        "succeeded": 0,
        "skipped_ssrf": 0,
        "skipped_unreachable": 0,
        "strategy_failed": 0,
        "total_cost_usd": 0.0,
        "logos_uploaded": 0,
        "heroes_uploaded": 0,
    }
    for o in outcomes:
        if o.succeeded and o.result is not None:
            summary["succeeded"] += 1
            summary["total_cost_usd"] += o.result.cost_usd
            if o.result.logo_r2_key:
                summary["logos_uploaded"] += 1
            if o.result.hero_r2_key:
                summary["heroes_uploaded"] += 1
            continue
        if o.error_category == ERROR_CATEGORY_SSRF:
            summary["skipped_ssrf"] += 1
        elif o.error_category == ERROR_CATEGORY_UNREACHABLE:
            summary["skipped_unreachable"] += 1
        elif o.error_category == ERROR_CATEGORY_STRATEGY:
            summary["strategy_failed"] += 1
    return summary


def _run_summary_markdown(
    *,
    mode: str,
    limit: int | None,
    started_at: datetime,
    finished_at: datetime,
    outcomes: list[ExtractorOutcome],
    summary: dict[str, Any],
) -> str:
    duration_s = (finished_at - started_at).total_seconds()
    failures = [o for o in outcomes if not o.succeeded]
    failure_rows = "\n".join(
        f"| `{o.lead_id}` | {o.url} | {o.error_category} | {o.error_reason} |"
        for o in failures[:20]
    ) or "_(none)_"

    avg_cost = (
        summary["total_cost_usd"] / summary["succeeded"]
        if summary["succeeded"]
        else 0.0
    )

    return f"""\
# Website Extractor — Run Summary

**Mode:** `{mode}`
**Limit:** `{limit}`
**Started:** `{started_at.isoformat()}`
**Finished:** `{finished_at.isoformat()}`
**Duration:** `{duration_s:.1f}s`

## Counts

| Metric | Value |
|---|---|
| Leads seen | {summary['targets_seen']} |
| Extractions persisted | {summary['succeeded']} |
| Logos uploaded to R2 | {summary['logos_uploaded']} |
| Heroes uploaded to R2 | {summary['heroes_uploaded']} |
| Skipped — SSRF | {summary['skipped_ssrf']} |
| Skipped — unreachable | {summary['skipped_unreachable']} |
| Strategy failures | {summary['strategy_failed']} |
| Total LLM cost | ${summary['total_cost_usd']:.4f} |
| Avg cost per persisted lead | ${avg_cost:.4f} |

## Failures (first 20)

| Lead ID | URL | Category | Reason |
|---|---|---|---|
{failure_rows}
"""


if __name__ == "__main__":
    asyncio.run(extract_websites(limit=5))
