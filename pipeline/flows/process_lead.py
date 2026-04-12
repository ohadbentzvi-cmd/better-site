"""Master orchestration flow.

Runs every agent in sequence for a single lead. Prefect handles retries,
failure logging, and observability.

Each agent is a Prefect task so individual steps can be replayed without
re-running the entire pipeline. All writes are idempotent (UPSERT-based),
so replays are safe.
"""

from __future__ import annotations

import uuid

import structlog
from prefect import flow

log = structlog.get_logger(__name__)


@flow(name="process_lead")
def process_lead(lead_id: uuid.UUID) -> None:
    """End-to-end pipeline for one lead.

    Stages:
        1. Scanner — score the existing site, decide pass/fail
        2. Extractor — pull content + visuals into ExtractionResult
        3. Builder — render the new preview site into Postgres
        4. Notify review queue (human approval before Sales Agent sends)
    """
    log.info("process_lead_start", lead_id=str(lead_id))

    # TODO (Phase 2+): import and call the real task functions
    # scan = scan_website(lead_id)
    # if not scan.pass_fail:
    #     mark_rejected(lead_id)
    #     return
    # extraction = extract_content(lead_id)
    # site = build_website(lead_id)
    # notify_review_queue(lead_id)

    raise NotImplementedError("process_lead flow is not yet implemented")
