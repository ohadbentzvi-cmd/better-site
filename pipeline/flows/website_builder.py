"""Website Builder flow — extraction → template content → sites row."""

from __future__ import annotations

import uuid

import structlog
from prefect import flow

log = structlog.get_logger(__name__)


@flow(name="website_builder")
def build_website(lead_id: uuid.UUID) -> None:
    """Phase 3 implementation TODO.

    1. Load extraction from DB
    2. Map extraction fields → template content.schema.json
    3. Optional Claude copy polish on tagline + headline
    4. Generate nanoid(12) slug, retry on collision
    5. UPSERT into sites, set expires_at = now() + settings.PREVIEW_EXPIRY_HOURS
    6. Update leads.status → review_pending
    7. All writes in a single transaction with rollback on failure
    """
    log.info("builder_start", lead_id=str(lead_id))
    raise NotImplementedError("build_website flow is not yet implemented")
