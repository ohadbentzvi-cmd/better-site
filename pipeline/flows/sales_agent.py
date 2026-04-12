"""Sales Agent flow — verify, render, send via the configured backend."""

from __future__ import annotations

import uuid

import structlog
from prefect import flow

log = structlog.get_logger(__name__)


@flow(name="sales_agent")
def send_sales_email(lead_id: uuid.UUID, sequence_step: int = 1) -> None:
    """Phase 5 implementation TODO.

    1. Load lead + site from DB (site must exist and not be expired)
    2. Check suppression list — hard gate
    3. ZeroBounce verify — hard gate (mark bad_email on failure)
    4. Render email HTML (subject, body, embedded preview screenshot URL)
    5. backend = get_backend(settings.SALES_AGENT_BACKEND)
    6. result = backend.send(payload)
    7. UPSERT emails row with the result
    8. Schedule follow-up at T+settings.FOLLOWUP_DELAY_HOURS if sequence_step == 1
    """
    log.info("sales_agent_start", lead_id=str(lead_id), sequence_step=sequence_step)
    raise NotImplementedError("send_sales_email flow is not yet implemented")
