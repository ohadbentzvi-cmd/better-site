"""Information Extractor flow.

Orchestrates the shared pre-fetch (Playwright render → HTML + screenshot)
then delegates the actual extraction to the configured ExtractionStrategy.
"""

from __future__ import annotations

import uuid

import structlog
from prefect import flow

log = structlog.get_logger(__name__)


@flow(name="website_extractor")
def extract_website(lead_id: uuid.UUID) -> None:
    """Phase 3 implementation TODO.

    1. Fetch lead.website_url (SSRF-safe)
    2. Playwright: render + full-page screenshot
    3. get_strategy(settings.EXTRACTION_STRATEGY).extract(url, html, screenshot)
    4. Upload images to R2
    5. UPSERT into extractions, update leads.status
    6. On strategy failure, fall back to gmb_first as a last resort
    """
    log.info("extractor_start", lead_id=str(lead_id))
    raise NotImplementedError("extract_website flow is not yet implemented")
