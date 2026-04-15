"""Source-agnostic ingestion pipeline.

Every ``RawLead`` from a ``LeadSource`` flows through this module:

    RawLead → canonicalize URL → SSRF check → UPSERT ops.leads → event log

The pipeline does not know which source produced the lead. Adding FMCSA
or Google Maps means writing a new ``LeadSource`` and registering it —
nothing here changes.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from pipeline.agents.lead_generator.base import LeadSource, RawLead
from pipeline.db import session_scope
from pipeline.models import Event, Lead, LeadStatus
from pipeline.utils.ssrf import UnsafeUrlError, assert_safe_url
from pipeline.utils.url import InvalidURLError, canonicalize_domain, canonicalize_url

log = structlog.get_logger(__name__)


@dataclass
class LeadGenSummary:
    """Counts for a single ``run_source`` invocation. Returned by the flow."""

    leads_seen: int = 0
    leads_inserted: int = 0
    leads_updated: int = 0
    leads_skipped_no_website: int = 0
    leads_skipped_invalid_url: int = 0
    leads_skipped_ssrf: int = 0
    leads_skipped_unsafe_dns: int = 0
    duplicate_domains: int = 0
    duplicate_profile_urls: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "leads_seen": self.leads_seen,
            "leads_inserted": self.leads_inserted,
            "leads_updated": self.leads_updated,
            "leads_skipped_no_website": self.leads_skipped_no_website,
            "leads_skipped_invalid_url": self.leads_skipped_invalid_url,
            "leads_skipped_ssrf": self.leads_skipped_ssrf,
            "leads_skipped_unsafe_dns": self.leads_skipped_unsafe_dns,
            "duplicate_domains": self.duplicate_domains,
            "duplicate_profile_urls": self.duplicate_profile_urls,
        }


@dataclass
class _IngestState:
    """Per-run in-memory dedup state; cheaper than round-tripping to the DB."""

    seen_domains_this_run: set[str] = field(default_factory=set)


async def run_source(
    source: LeadSource,
    *,
    vertical: str,
    state: str,
    city: str,
    max_pages: int | None = None,
) -> LeadGenSummary:
    """Drive a source to completion and ingest every yielded ``RawLead``.

    Sequential on purpose — concurrency is a post-MVP optimization.
    """
    summary = LeadGenSummary()
    ingest_state = _IngestState()
    async for raw in source.fetch(
        vertical=vertical, state=state, city=city, max_pages=max_pages
    ):
        summary.leads_seen += 1
        # Off-load the blocking UPSERT so we don't stall the event loop
        # while the source is waiting on its next page.
        await asyncio.to_thread(
            ingest_raw_lead, raw, summary=summary, ingest_state=ingest_state
        )

    # No DB row for the run summary — Prefect captures the flow result +
    # structlog emits the same numbers. If we need queryable run history
    # later, add an ops.scrape_runs table; don't attach summary events to
    # an arbitrary lead.
    log.info(
        "lead_generator.run_complete",
        source=source.name,
        vertical=vertical,
        state=state,
        city=city,
        **summary.as_dict(),
    )
    return summary


def ingest_raw_lead(
    raw: RawLead,
    *,
    summary: LeadGenSummary | None = None,
    ingest_state: _IngestState | None = None,
) -> None:
    """Canonicalize + SSRF-check + UPSERT one raw lead.

    Idempotent: safe to call multiple times with the same input. Prefect
    task retries rely on this.
    """
    summary = summary or LeadGenSummary()
    ingest_state = ingest_state or _IngestState()

    if not raw.website_url:
        summary.leads_skipped_no_website += 1
        log.info(
            "lead_generator.skip_no_website",
            source=raw.source,
            business_name=raw.business_name,
        )
        return

    try:
        website = canonicalize_url(raw.website_url)
        domain = canonicalize_domain(website)
    except InvalidURLError as e:
        summary.leads_skipped_invalid_url += 1
        log.warning(
            "lead_generator.skip_invalid_url",
            source=raw.source,
            business_name=raw.business_name,
            raw_url=raw.website_url,
            error=str(e),
        )
        return

    try:
        assert_safe_url(website)
    except UnsafeUrlError as e:
        summary.leads_skipped_ssrf += 1
        log.warning(
            "lead_generator.skip_ssrf",
            source=raw.source,
            business_name=raw.business_name,
            raw_url=raw.website_url,
            canonical_domain=domain,
            error=str(e),
        )
        return

    if domain in ingest_state.seen_domains_this_run:
        summary.duplicate_domains += 1
        log.info(
            "lead_generator.duplicate_domain_in_run",
            canonical_domain=domain,
            business_name=raw.business_name,
        )
        return
    ingest_state.seen_domains_this_run.add(domain)

    result = _upsert_lead(raw=raw, website=website, domain=domain)
    if result == "inserted":
        summary.leads_inserted += 1
    else:
        summary.leads_updated += 1


def _upsert_lead(*, raw: RawLead, website: str, domain: str) -> str:
    """Insert or update by ``canonical_domain``. Returns 'inserted' or 'updated'."""
    incoming_metadata: dict[str, Any] = dict(raw.source_metadata or {})
    incoming_metadata.setdefault("canonical_website", website)

    values = {
        "business_name": raw.business_name,
        "vertical": raw.vertical,
        "website_url": website,
        "canonical_domain": domain,
        "email": raw.email,
        "email_source": raw.email_source,
        "phone": raw.phone,
        "city": raw.city,
        "state": raw.state,
        "country": raw.country,
        "source": raw.source,
        "source_metadata": incoming_metadata,
        "status": LeadStatus.new,
    }

    with session_scope() as session:
        existed = _row_exists_by_domain(session, domain)
        stmt = pg_insert(Lead).values(**values)

        # ON CONFLICT: prefer existing non-null values (don't overwrite contact
        # info with a second source that has less). source_metadata overwrites
        # for now; proper deep-merge lives in a follow-up when we add FMCSA.
        update_set: dict[str, Any] = {
            "business_name": stmt.excluded.business_name,
            "vertical": stmt.excluded.vertical,
            "website_url": stmt.excluded.website_url,
            "phone": func.coalesce(stmt.excluded.phone, Lead.__table__.c.phone),
            "email": func.coalesce(stmt.excluded.email, Lead.__table__.c.email),
            "email_source": func.coalesce(stmt.excluded.email_source, Lead.__table__.c.email_source),
            "city": func.coalesce(stmt.excluded.city, Lead.__table__.c.city),
            "state": func.coalesce(stmt.excluded.state, Lead.__table__.c.state),
            "country": stmt.excluded.country,
            "source_metadata": stmt.excluded.source_metadata,
        }

        stmt = stmt.on_conflict_do_update(
            index_elements=["canonical_domain"],
            set_=update_set,
        )
        session.execute(stmt)
        _write_upsert_event(
            session,
            domain=domain,
            source=raw.source,
            was_insert=not existed,
            business_name=raw.business_name,
        )
        session.commit()

    log.info(
        "lead_generator.upsert",
        canonical_domain=domain,
        source=raw.source,
        action="inserted" if not existed else "updated",
        business_name=raw.business_name,
    )
    return "inserted" if not existed else "updated"


def _row_exists_by_domain(session: Session, domain: str) -> bool:
    return (
        session.scalar(select(Lead.id).where(Lead.canonical_domain == domain))
        is not None
    )


def _write_upsert_event(
    session: Session, *, domain: str, source: str, was_insert: bool, business_name: str
) -> None:
    lead_id = session.scalar(
        select(Lead.id).where(Lead.canonical_domain == domain)
    )
    if lead_id is None:
        return
    session.add(
        Event(
            lead_id=lead_id,
            event_type="lead_generator.upsert",
            payload={
                "source": source,
                "action": "inserted" if was_insert else "updated",
                "business_name": business_name,
                "canonical_domain": domain,
            },
        )
    )


__all__ = ["LeadGenSummary", "ingest_raw_lead", "run_source"]
