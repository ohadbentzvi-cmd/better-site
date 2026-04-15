"""Lead Generator flow.

Source-pluggable Prefect flow. Today ``source="bbb"`` is the only
registered value; FMCSA / Google Maps plug in later via
``pipeline.agents.lead_generator.sources``.
"""

from __future__ import annotations

import structlog
from prefect import flow

from pipeline.agents.lead_generator.pipeline import LeadGenSummary, run_source
from pipeline.agents.lead_generator.sources import get_source

log = structlog.get_logger(__name__)


@flow(name="lead-generation")
async def generate_leads(
    source: str = "bbb",
    vertical: str = "movers",
    state: str = "TX",
    city: str = "Houston",
    max_pages: int | None = None,
) -> dict[str, int]:
    """Ingest leads from ``source`` for (vertical, state, city).

    Returns the ``LeadGenSummary`` as a plain dict so Prefect can persist
    it as the run result.
    """
    log.info(
        "lead_generation_start",
        source=source,
        vertical=vertical,
        state=state,
        city=city,
        max_pages=max_pages,
    )

    lead_source = get_source(source)
    summary: LeadGenSummary = await run_source(
        lead_source,
        vertical=vertical,
        state=state,
        city=city,
        max_pages=max_pages,
    )
    return summary.as_dict()


if __name__ == "__main__":
    import asyncio

    asyncio.run(generate_leads())
