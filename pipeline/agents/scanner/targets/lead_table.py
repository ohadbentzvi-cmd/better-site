"""Pull unscanned leads from ``ops.leads``."""

from __future__ import annotations

from collections.abc import AsyncIterator

import structlog
from sqlalchemy import select
from sqlalchemy.orm import aliased

from pipeline.agents.scanner.base import TargetUrl
from pipeline.db import session_scope
from pipeline.models import Lead, Scan

log = structlog.get_logger(__name__)


class LeadTableTarget:
    """Yields ``TargetUrl`` for each lead in ``ops.leads`` without a scan row.

    Attached ``lead_id`` so the ingest pipeline can UPSERT the scan result.
    """

    name = "leads"

    def __init__(self, limit: int | None = 50) -> None:
        self.limit = limit

    async def iter_targets(self) -> AsyncIterator[TargetUrl]:
        targets = self._load()
        log.info("scanner.target.leads_loaded", count=len(targets), limit=self.limit)
        for t in targets:
            yield t

    def _load(self) -> list[TargetUrl]:
        scan_alias = aliased(Scan)
        stmt = (
            select(Lead.id, Lead.website_url)
            .outerjoin(scan_alias, scan_alias.lead_id == Lead.id)
            .where(scan_alias.id.is_(None))
            .where(Lead.website_url.isnot(None))
            .order_by(Lead.created_at.asc())
        )
        if self.limit is not None:
            stmt = stmt.limit(self.limit)
        with session_scope() as session:
            rows = session.execute(stmt).all()
        return [
            TargetUrl(url=r.website_url, lead_id=r.id)
            for r in rows
            if r.website_url
        ]


__all__ = ["LeadTableTarget"]
