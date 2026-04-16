"""Lead Generator — batch flow.

Runs the single-city lead-gen loop for every ``(vertical, state, city)`` row
in a CSV. Sequential on purpose: BBB is one origin, parallel cities means
parallel httpx clients from one IP, which is the easiest way to earn a 403.

Resumability is operator-driven: if a run dies mid-batch, the operator edits
the CSV (or splits it into chunks) and reruns. UPSERT idempotency makes
reruns correct; chunking makes them fast.

Circuit breaker: one 403 from BBB fails that city only. A second 403 in the
same run raises ``BBBBatchAbortedError`` and halts — two blocks in a row
means our IP is flagged, and continuing just deepens the ban.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import structlog
from prefect import flow, get_run_logger, task
from prefect.artifacts import create_markdown_artifact

from pipeline.agents.lead_generator.pipeline import LeadGenSummary, run_source
from pipeline.agents.lead_generator.sources import get_source
from pipeline.agents.lead_generator.sources.bbb import (
    BBBBatchAbortedError,
    BBBBlockedError,
    BBBNotFoundError,
    BBBParseError,
    BBBRateLimitError,
)
from pipeline.agents.lead_generator.targets import (
    CityTarget,
    InvalidTargetsFileError,
    load_targets,
)
from pipeline.observability import configure as configure_logging

log = structlog.get_logger(__name__)

_DEFAULT_TARGETS_CSV = "pipeline/targets/movers_us.csv"


@dataclass
class CityResult:
    target: CityTarget
    status: str  # completed | failed | blocked | aborted
    duration_s: float
    summary: dict[str, int] | None
    error: str | None


@task(name="lead-generation-city", retries=0)
async def _run_city(
    *,
    source: str,
    vertical: str,
    state: str,
    city: str,
    max_pages: int | None,
) -> dict[str, int]:
    """Per-city work, wrapped as a Prefect task for UI visibility.

    No task-level retries: BBB-internal tenacity already handles transient
    errors, and a Prefect retry would re-walk pagination from page 1.
    """
    lead_source = get_source(source)
    summary: LeadGenSummary = await run_source(
        lead_source,
        vertical=vertical,
        state=state,
        city=city,
        max_pages=max_pages,
    )
    return summary.as_dict()


@flow(name="lead-generation-batch")
async def generate_leads_batch(
    source: str = "bbb",
    targets_csv: str = _DEFAULT_TARGETS_CSV,
    max_pages_per_city: int | None = None,
    abort_on_repeated_block: int = 2,
) -> dict[str, Any]:
    """Run lead-gen across every ``(vertical, state, city)`` row in ``targets_csv``.

    Returns the aggregate summary plus a per-city result list as a plain dict
    so Prefect can persist it as the run result.
    """
    configure_logging()
    run_log = get_run_logger()

    if abort_on_repeated_block < 1:
        raise ValueError(
            f"abort_on_repeated_block must be >= 1 (got {abort_on_repeated_block})"
        )

    targets = load_targets(Path(targets_csv))
    run_log.info(
        "lead-generation-batch starting | source=%s targets=%d max_pages_per_city=%s abort_on_repeated_block=%d",
        source, len(targets), max_pages_per_city, abort_on_repeated_block,
    )
    log.info(
        "lead_generator_batch_start",
        source=source,
        targets_csv=str(targets_csv),
        target_count=len(targets),
        max_pages_per_city=max_pages_per_city,
        abort_on_repeated_block=abort_on_repeated_block,
    )

    started_at = datetime.now(tz=timezone.utc)
    results: list[CityResult] = []
    totals = LeadGenSummary()
    blocked_count = 0
    aborted = False

    for index, target in enumerate(targets, start=1):
        run_log.info(
            "lead-generation-batch city %d/%d | %s", index, len(targets), target.label(),
        )
        city_started = datetime.now(tz=timezone.utc)
        try:
            summary_dict = await _run_city(
                source=source,
                vertical=target.vertical,
                state=target.state,
                city=target.city,
                max_pages=max_pages_per_city,
            )
        except BBBBlockedError as exc:
            blocked_count += 1
            duration_s = (datetime.now(tz=timezone.utc) - city_started).total_seconds()
            run_log.warning(
                "lead-generation-batch blocked | %s (%d/%d)",
                target.label(), blocked_count, abort_on_repeated_block,
            )
            log.error(
                "lead_generator_batch.city_blocked",
                target=target.label(),
                blocked_count=blocked_count,
                error=str(exc),
            )
            results.append(
                CityResult(
                    target=target,
                    status="blocked",
                    duration_s=duration_s,
                    summary=None,
                    error=str(exc),
                )
            )
            if blocked_count >= abort_on_repeated_block:
                aborted = True
                run_log.error(
                    "lead-generation-batch aborting | %d blocks in this run",
                    blocked_count,
                )
                for remaining in targets[index:]:
                    results.append(
                        CityResult(
                            target=remaining,
                            status="aborted",
                            duration_s=0.0,
                            summary=None,
                            error="batch aborted before this city ran",
                        )
                    )
                break
            continue
        except (BBBParseError, BBBNotFoundError, BBBRateLimitError) as exc:
            duration_s = (datetime.now(tz=timezone.utc) - city_started).total_seconds()
            log.warning(
                "lead_generator_batch.city_failed",
                target=target.label(),
                error_class=type(exc).__name__,
                error=str(exc),
            )
            results.append(
                CityResult(
                    target=target,
                    status="failed",
                    duration_s=duration_s,
                    summary=None,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        except httpx.HTTPError as exc:
            duration_s = (datetime.now(tz=timezone.utc) - city_started).total_seconds()
            log.warning(
                "lead_generator_batch.city_http_error",
                target=target.label(),
                error_class=type(exc).__name__,
                error=str(exc),
            )
            results.append(
                CityResult(
                    target=target,
                    status="failed",
                    duration_s=duration_s,
                    summary=None,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            continue

        duration_s = (datetime.now(tz=timezone.utc) - city_started).total_seconds()
        _accumulate(totals, summary_dict)
        results.append(
            CityResult(
                target=target,
                status="completed",
                duration_s=duration_s,
                summary=summary_dict,
                error=None,
            )
        )
        run_log.info(
            "lead-generation-batch city complete | %s inserted=%d seen=%d duration=%.1fs",
            target.label(),
            summary_dict["leads_inserted"],
            summary_dict["leads_seen"],
            duration_s,
        )

    finished_at = datetime.now(tz=timezone.utc)
    totals_dict = totals.as_dict()

    await create_markdown_artifact(
        key="lead-generation-batch-summary",
        markdown=_summary_markdown(
            source=source,
            targets_csv=str(targets_csv),
            max_pages_per_city=max_pages_per_city,
            abort_on_repeated_block=abort_on_repeated_block,
            started_at=started_at,
            finished_at=finished_at,
            totals=totals_dict,
            results=results,
            aborted=aborted,
        ),
        description=f"Lead generation batch — {source}, {len(results)} cities",
    )

    run_log.info(
        "lead-generation-batch complete | cities=%d inserted=%d updated=%d seen=%d blocked=%d aborted=%s",
        len(results),
        totals_dict["leads_inserted"],
        totals_dict["leads_updated"],
        totals_dict["leads_seen"],
        blocked_count,
        aborted,
    )

    if aborted:
        raise BBBBatchAbortedError(
            f"batch aborted after {blocked_count} BBB blocks in one run"
        )

    return {
        "totals": totals_dict,
        "city_count": len(results),
        "cities_completed": sum(1 for r in results if r.status == "completed"),
        "cities_failed": sum(1 for r in results if r.status == "failed"),
        "cities_blocked": sum(1 for r in results if r.status == "blocked"),
        "cities_aborted": sum(1 for r in results if r.status == "aborted"),
    }


def _accumulate(totals: LeadGenSummary, summary_dict: dict[str, int]) -> None:
    totals.leads_seen += summary_dict.get("leads_seen", 0)
    totals.leads_inserted += summary_dict.get("leads_inserted", 0)
    totals.leads_updated += summary_dict.get("leads_updated", 0)
    totals.leads_skipped_no_website += summary_dict.get("leads_skipped_no_website", 0)
    totals.leads_skipped_invalid_url += summary_dict.get("leads_skipped_invalid_url", 0)
    totals.leads_skipped_ssrf += summary_dict.get("leads_skipped_ssrf", 0)
    totals.leads_skipped_unsafe_dns += summary_dict.get("leads_skipped_unsafe_dns", 0)
    totals.duplicate_domains += summary_dict.get("duplicate_domains", 0)
    totals.duplicate_profile_urls += summary_dict.get("duplicate_profile_urls", 0)


def _summary_markdown(
    *,
    source: str,
    targets_csv: str,
    max_pages_per_city: int | None,
    abort_on_repeated_block: int,
    started_at: datetime,
    finished_at: datetime,
    totals: dict[str, int],
    results: list[CityResult],
    aborted: bool,
) -> str:
    duration_s = (finished_at - started_at).total_seconds()

    status_counts: dict[str, int] = {}
    for r in results:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1

    totals_rows = [
        ("leads_seen", "Leads seen"),
        ("leads_inserted", "New leads inserted"),
        ("leads_updated", "Existing leads updated"),
        ("leads_skipped_no_website", "Skipped — no website"),
        ("leads_skipped_invalid_url", "Skipped — invalid URL"),
        ("leads_skipped_ssrf", "Skipped — SSRF unsafe"),
        ("duplicate_domains", "Duplicates collapsed"),
    ]
    totals_table = "\n".join(
        f"| {label} | {totals.get(key, 0)} |" for key, label in totals_rows
    )

    per_city_rows = [
        "| City | State | Vertical | Status | Inserted | Seen | Duration | Error |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        inserted = r.summary["leads_inserted"] if r.summary else 0
        seen = r.summary["leads_seen"] if r.summary else 0
        err = (r.error or "").replace("|", "\\|")[:120]
        per_city_rows.append(
            f"| {r.target.city} | {r.target.state} | {r.target.vertical} | "
            f"{r.status} | {inserted} | {seen} | {r.duration_s:.1f}s | {err} |"
        )
    per_city_table = "\n".join(per_city_rows)

    aborted_banner = "\n**⚠️ BATCH ABORTED — see blocked rows below**\n" if aborted else ""

    return f"""\
# Lead Generation Batch Summary
{aborted_banner}
**Source:** `{source}` · **Targets CSV:** `{targets_csv}`
**Max pages/city:** `{max_pages_per_city}` · **Abort threshold:** `{abort_on_repeated_block}` blocks

**Started:** `{started_at.isoformat()}`
**Finished:** `{finished_at.isoformat()}`
**Duration:** `{duration_s:.1f}s`

## Per-city status

{_status_counts_line(status_counts, len(results))}

## Totals

| Metric | Value |
|---|---|
{totals_table}

## Cities

{per_city_table}
"""


def _status_counts_line(counts: dict[str, int], total: int) -> str:
    parts = [f"**{total} cities** —"]
    for status in ("completed", "failed", "blocked", "aborted"):
        if counts.get(status, 0) > 0:
            parts.append(f"{counts[status]} {status}")
    return " ".join(parts) if len(parts) > 1 else f"**{total} cities**"


__all__ = ["CityResult", "generate_leads_batch"]


if __name__ == "__main__":
    import asyncio

    asyncio.run(generate_leads_batch())
