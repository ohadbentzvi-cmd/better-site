"""Scanner orchestration.

- ``scan_url`` runs the three checks per URL. PageSpeed runs concurrently
  with the browser session; HTTP checks run after the browser is done.
- ``scan_target`` wraps ``scan_url`` with UPSERT to ``ops.scans`` when the
  target is a real lead.
- ``run_scanner`` drives a ``ScanTarget`` to completion.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from pipeline.agents.scanner.base import (
    BrowserCheckResult,
    Finding,
    HttpCheckResult,
    PageSpeedData,
    ScanResult,
    ScanTarget,
    TargetUrl,
)
from pipeline.agents.scanner.checks.browser import fetch_browser_data
from pipeline.agents.scanner.checks.http import fetch_http_checks
from pipeline.agents.scanner.checks.pagespeed import fetch_pagespeed
from pipeline.agents.scanner.scoring import PASS_FAIL_THRESHOLD, score_scan
from pipeline.config import get_settings
from pipeline.db import session_scope
from pipeline.models import Scan
from pipeline.utils.ssrf import UnsafeUrlError, assert_safe_url

log = structlog.get_logger(__name__)


@dataclass
class ScannerSummary:
    targets_seen: int = 0
    scans_persisted: int = 0
    artifacts_only: int = 0  # URL-list mode with no matching lead
    skipped_ssrf: int = 0
    skipped_unreachable: int = 0
    partial_scans: int = 0
    per_url_results: list[ScanResult] = field(default_factory=list)

    def as_dict(self) -> dict[str, int]:
        return {
            "targets_seen": self.targets_seen,
            "scans_persisted": self.scans_persisted,
            "artifacts_only": self.artifacts_only,
            "skipped_ssrf": self.skipped_ssrf,
            "skipped_unreachable": self.skipped_unreachable,
            "partial_scans": self.partial_scans,
        }


async def run_scanner(target: ScanTarget) -> ScannerSummary:
    summary = ScannerSummary()
    async for tgt in target.iter_targets():
        summary.targets_seen += 1
        try:
            result = await scan_target(tgt)
        except UnsafeUrlError as e:
            summary.skipped_ssrf += 1
            log.warning("scanner.skip_ssrf", url=tgt.url, error=str(e))
            continue
        if result is None:
            summary.skipped_unreachable += 1
            continue
        summary.per_url_results.append(result)
        if result.scan_partial:
            summary.partial_scans += 1
        if tgt.lead_id is not None:
            summary.scans_persisted += 1
        else:
            summary.artifacts_only += 1
    log.info("scanner.run_complete", source=target.name, **summary.as_dict())
    return summary


async def scan_target(target: TargetUrl) -> ScanResult | None:
    """Scan one URL. Return None only for truly unreachable sites."""
    result = await scan_url(target.url)
    if result is None:
        return None
    if target.lead_id is not None:
        await asyncio.to_thread(_upsert_scan, target.lead_id, result)
    return result


async def scan_url(url: str) -> ScanResult | None:
    """Run PageSpeed + Playwright + HTTP against ``url``.

    PageSpeed is initiated in parallel with the browser session (PageSpeed
    runs on Google's servers; it doesn't hit the site from our worker).
    HTTP checks wait for the browser to finish so we don't double-hammer
    the site from our own IP.
    """
    assert_safe_url(url)
    settings = get_settings()

    log.info("scanner.scan_start", url=url)

    pagespeed_task = asyncio.create_task(
        fetch_pagespeed(url, api_key=settings.PAGESPEED_API_KEY or None)
    )

    try:
        browser_result = await fetch_browser_data(url)
    except Exception as e:  # noqa: BLE001 — last-resort sentinel
        log.error("scanner.browser_fatal", url=url, error=str(e), exc_info=True)
        browser_result = BrowserCheckResult(available=False, error_reason=str(e))

    http_result = await fetch_http_checks(url)
    pagespeed_result = await pagespeed_task

    scored = score_scan(pagespeed_result, browser_result, http_result)

    result = ScanResult(
        url=url,
        scanned_url=url,
        score_performance=scored["score_performance"],
        score_seo=scored["score_seo"],
        score_ai_readiness=scored["score_ai_readiness"],
        score_security=scored["score_security"],
        overall=scored["overall"],
        scan_partial=scored["scan_partial"],
        pagespeed_available=pagespeed_result.available,
        pagespeed_mobile=_perf_of(pagespeed_result, "mobile"),
        pagespeed_desktop=_perf_of(pagespeed_result, "desktop"),
        has_ssl=url.lower().startswith("https://"),
        has_mobile=browser_result.has_viewport_meta,
        has_analytics=False,  # unused in v1; placeholder for future analytics detection
        raw_metrics=scored["raw_metrics"],
        findings=scored["findings"],
    )
    log.info(
        "scanner.scan_complete",
        url=url,
        overall=result.overall,
        scan_partial=result.scan_partial,
        finding_count=len(result.findings),
    )
    return result


def _perf_of(ps: PageSpeedData, strategy: str) -> int | None:
    r = getattr(ps, strategy, None)
    if r is None:
        return None
    return r.performance_score


# ── DB UPSERT ────────────────────────────────────────────────────────────────


def _upsert_scan(lead_id: uuid.UUID, result: ScanResult) -> None:
    """INSERT ... ON CONFLICT (lead_id) DO UPDATE. Idempotent per Prefect contract."""
    findings_json = [f.model_dump() for f in result.findings]
    pass_fail = result.overall is not None and result.overall >= PASS_FAIL_THRESHOLD
    values: dict[str, Any] = {
        "lead_id": lead_id,
        "scanned_url": result.scanned_url,
        "score": result.overall,
        "pass_fail": pass_fail,
        "score_performance": result.score_performance,
        "score_seo": result.score_seo,
        "score_ai_readiness": result.score_ai_readiness,
        "score_security": result.score_security,
        "scan_partial": result.scan_partial,
        "pagespeed_available": result.pagespeed_available,
        "pagespeed_mobile": result.pagespeed_mobile,
        "pagespeed_desktop": result.pagespeed_desktop,
        "has_ssl": result.has_ssl,
        "has_mobile": result.has_mobile,
        "has_analytics": result.has_analytics,
        "issues_json": findings_json,
        "raw_metrics": result.raw_metrics,
    }
    stmt = pg_insert(Scan).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["lead_id"],
        set_={
            k: stmt.excluded[k]
            for k in values
            if k != "lead_id"
        },
    )
    with session_scope() as session:
        session.execute(stmt)
        session.commit()


__all__ = ["ScannerSummary", "run_scanner", "scan_target", "scan_url"]
