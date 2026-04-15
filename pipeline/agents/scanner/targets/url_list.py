"""Explicit URL list — for ad-hoc scans and "re-scan this specific lead".

If the URL's canonical domain matches an existing lead, we opportunistically
attach the ``lead_id`` so the ingest pipeline UPSERTs to ``ops.scans``.
Otherwise the scan emits an artifact-only result (no DB write).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterable

import structlog
from sqlalchemy import select

from pipeline.agents.scanner.base import TargetUrl
from pipeline.db import session_scope
from pipeline.models import Lead
from pipeline.utils.url import InvalidURLError, canonicalize_domain

log = structlog.get_logger(__name__)


class UrlListTarget:
    """Yields ``TargetUrl`` for each URL. Matches against ops.leads by domain."""

    name = "urls"

    def __init__(self, urls: Iterable[str]) -> None:
        self.urls: list[str] = [u for u in urls if u and u.strip()]

    async def iter_targets(self) -> AsyncIterator[TargetUrl]:
        domain_to_lead = self._load_lead_lookup(self.urls)
        for raw_url in self.urls:
            lead_id = self._match_lead(raw_url, domain_to_lead)
            yield TargetUrl(url=raw_url, lead_id=lead_id)

    @staticmethod
    def _match_lead(
        url: str, lookup: dict[str, uuid.UUID]
    ) -> uuid.UUID | None:
        try:
            domain = canonicalize_domain(url)
        except InvalidURLError:
            return None
        return lookup.get(domain)

    @staticmethod
    def _load_lead_lookup(urls: list[str]) -> dict[str, uuid.UUID]:
        domains: set[str] = set()
        for u in urls:
            try:
                domains.add(canonicalize_domain(u))
            except InvalidURLError:
                continue
        if not domains:
            return {}
        with session_scope() as session:
            rows = session.execute(
                select(Lead.canonical_domain, Lead.id).where(
                    Lead.canonical_domain.in_(domains)
                )
            ).all()
        return {r.canonical_domain: r.id for r in rows}


__all__ = ["UrlListTarget"]
