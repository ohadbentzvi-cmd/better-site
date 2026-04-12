"""Website Scanner flow — scores the lead's existing site."""

from __future__ import annotations

import uuid

import structlog
from prefect import flow

log = structlog.get_logger(__name__)


@flow(name="website_scanner")
def scan_website(lead_id: uuid.UUID) -> None:
    """Phase 2 implementation TODO.

    1. Fetch lead.website_url
    2. PageSpeed Insights call (mobile + desktop)
    3. HTTP scraper for SSL, favicon, meta tags, H1, viewport, analytics
    4. Score calculation — weighted across all metrics
    5. Issue bullet formatter
    6. UPSERT into scans, update leads.status
    """
    log.info("scanner_start", lead_id=str(lead_id))
    raise NotImplementedError("scan_website flow is not yet implemented")
