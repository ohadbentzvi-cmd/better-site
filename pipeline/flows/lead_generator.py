"""Lead Generator flow.

Source-pluggable Prefect flow. Today ``source="bbb"`` is the only
registered value; FMCSA / Google Maps plug in later via
``pipeline.agents.lead_generator.sources``.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from prefect import flow, get_run_logger
from prefect.artifacts import create_markdown_artifact

from pipeline.agents.lead_generator.pipeline import LeadGenSummary, run_source
from pipeline.agents.lead_generator.sources import get_source
from pipeline.observability import configure as configure_logging

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
    it as the run result. Also emits a markdown artifact with the run
    summary for one-click visibility in the Prefect UI.
    """
    configure_logging()
    run_log = get_run_logger()
    run_log.info(
        "lead-generation starting | source=%s vertical=%s state=%s city=%s max_pages=%s",
        source, vertical, state, city, max_pages,
    )
    log.info(
        "lead_generation_start",
        source=source,
        vertical=vertical,
        state=state,
        city=city,
        max_pages=max_pages,
    )

    lead_source = get_source(source)
    started_at = datetime.now(tz=timezone.utc)
    summary: LeadGenSummary = await run_source(
        lead_source,
        vertical=vertical,
        state=state,
        city=city,
        max_pages=max_pages,
    )
    finished_at = datetime.now(tz=timezone.utc)

    summary_dict = summary.as_dict()
    run_log.info(
        "lead-generation complete | inserted=%d updated=%d seen=%d skipped_no_website=%d duplicate_domains=%d",
        summary_dict["leads_inserted"],
        summary_dict["leads_updated"],
        summary_dict["leads_seen"],
        summary_dict["leads_skipped_no_website"],
        summary_dict["duplicate_domains"],
    )

    await create_markdown_artifact(
        key="lead-generation-summary",
        markdown=_summary_markdown(
            source=source,
            vertical=vertical,
            state=state,
            city=city,
            max_pages=max_pages,
            started_at=started_at,
            finished_at=finished_at,
            summary=summary_dict,
        ),
        description=f"Lead generation — {source} / {vertical} / {city}, {state}",
    )

    return summary_dict


def _summary_markdown(
    *,
    source: str,
    vertical: str,
    state: str,
    city: str,
    max_pages: int | None,
    started_at: datetime,
    finished_at: datetime,
    summary: dict[str, int],
) -> str:
    duration_s = (finished_at - started_at).total_seconds()
    rows = [
        ("leads_seen", "Leads seen (yielded by source)"),
        ("leads_inserted", "New leads inserted"),
        ("leads_updated", "Existing leads updated"),
        ("leads_skipped_no_website", "Skipped — no website"),
        ("leads_skipped_invalid_url", "Skipped — invalid URL"),
        ("leads_skipped_ssrf", "Skipped — SSRF unsafe"),
        ("leads_skipped_unsafe_dns", "Skipped — unsafe DNS"),
        ("duplicate_domains", "Duplicates collapsed in run"),
        ("duplicate_profile_urls", "Duplicate profile URLs"),
    ]
    table = "\n".join(
        f"| {label} | {summary.get(key, 0)} |" for key, label in rows
    )
    return f"""\
# Lead Generation Summary

**Source:** `{source}` · **Vertical:** `{vertical}` · **City:** `{city}, {state}` · **Max pages:** `{max_pages}`

**Started:** `{started_at.isoformat()}`
**Finished:** `{finished_at.isoformat()}`
**Duration:** `{duration_s:.1f}s`

## Counts

| Metric | Value |
|---|---|
{table}
"""


if __name__ == "__main__":
    import asyncio

    asyncio.run(generate_leads())
