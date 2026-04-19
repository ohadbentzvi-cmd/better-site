"""Website Scanner flow.

Two input modes:

- URL-list mode: ``urls=[...]``. Scans each URL; if the URL's canonical
  domain matches an existing lead, the result UPSERTs to ``ops.scans``.
  Otherwise it emits an artifact-only scan.
- Leads-table mode: ``urls=None`` (default). Pulls the next ``limit``
  unscanned leads from ``ops.leads`` and scans them.

Each URL produces a markdown artifact with scores + findings. A final
run-summary artifact aggregates the batch.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from prefect import flow, get_run_logger
from prefect.artifacts import create_markdown_artifact

from pipeline.agents.scanner.base import Finding, ScanResult
from pipeline.agents.scanner.pipeline import ScannerSummary, run_scanner
from pipeline.agents.scanner.targets import LeadTableTarget, UrlListTarget
from pipeline.observability import configure as configure_logging

log = structlog.get_logger(__name__)


@flow(name="site-scan")
async def scan_sites(
    urls: list[str] | None = None,
    limit: int | None = 50,
) -> dict[str, int]:
    """Scan a batch of URLs. See module docstring for input-mode details."""
    configure_logging()
    run_log = get_run_logger()

    started_at = datetime.now(tz=timezone.utc)
    if urls:
        target = UrlListTarget(urls)
        run_log.info("site-scan starting | mode=url_list count=%d", len(urls))
    else:
        target = LeadTableTarget(limit=limit)
        run_log.info("site-scan starting | mode=leads_table limit=%s", limit)

    summary: ScannerSummary = await run_scanner(target)
    finished_at = datetime.now(tz=timezone.utc)

    for result in summary.per_url_results:
        await create_markdown_artifact(
            key=None,  # per-url artifacts are throwaway — no key = ephemeral
            markdown=_per_url_markdown(result),
            description=f"Scan · {result.url} · overall={result.overall}",
        )

    await create_markdown_artifact(
        key="site-scan-summary",
        markdown=_run_summary_markdown(
            target_name=target.name,
            urls=urls,
            limit=limit,
            started_at=started_at,
            finished_at=finished_at,
            summary=summary,
        ),
        description=f"Scanner run — {target.name} — {summary.scans_persisted + summary.artifacts_only} URLs",
    )

    run_log.info(
        "site-scan complete | targets=%d persisted=%d artifacts_only=%d partial=%d",
        summary.targets_seen, summary.scans_persisted,
        summary.artifacts_only, summary.partial_scans,
    )
    return summary.as_dict()


# ── Markdown builders ────────────────────────────────────────────────────────


def _per_url_markdown(r: ScanResult) -> str:
    dim_rows = [
        ("Performance (45%)", r.score_performance),
        ("SEO (20%)", r.score_seo),
        ("AI-Readiness (20%)", r.score_ai_readiness),
        ("Security (15%)", r.score_security),
    ]
    dim_table = "\n".join(
        f"| {label} | {'—' if v is None else v} |" for label, v in dim_rows
    )
    findings_md = _findings_markdown(r.findings)
    overall = "—" if r.overall is None else str(r.overall)
    partial_note = "\n\n> ⚠️ Partial scan — at least one dimension was unmeasurable." if r.scan_partial else ""
    return f"""\
# Scan — `{r.url}`

**Overall score:** `{overall}` / 100{partial_note}

## Dimension scores

| Dimension | Score |
|---|---|
{dim_table}

## Findings ({len(r.findings)})

{findings_md}

## Raw metrics

```
{_raw_metrics_block(r)}
```
"""


def _findings_markdown(findings: list[Finding]) -> str:
    if not findings:
        return "_No findings._"
    lines: list[str] = []
    order = {"high": 0, "medium": 1, "low": 2}
    for f in sorted(findings, key=lambda x: order.get(x.severity, 3)):
        lines.append(
            f"- **[{f.severity.upper()} · {f.category}]** {f.smb_message}\n"
            f"  _{f.technical_detail}_"
        )
    return "\n".join(lines)


def _raw_metrics_block(r: ScanResult) -> str:
    if not r.raw_metrics:
        return "(no metrics captured)"
    items = []
    for k, v in r.raw_metrics.items():
        if v is None:
            continue
        if isinstance(v, float):
            items.append(f"{k}: {v:.2f}")
        else:
            items.append(f"{k}: {v}")
    return "\n".join(items) if items else "(no metrics captured)"


def _run_summary_markdown(
    *,
    target_name: str,
    urls: list[str] | None,
    limit: int | None,
    started_at: datetime,
    finished_at: datetime,
    summary: ScannerSummary,
) -> str:
    duration_s = (finished_at - started_at).total_seconds()
    scores = [r.overall for r in summary.per_url_results if r.overall is not None]
    avg_overall = (sum(scores) / len(scores)) if scores else None
    buckets = {"0-40": 0, "40-70": 0, "70-100": 0, "unknown": 0}
    for r in summary.per_url_results:
        if r.overall is None:
            buckets["unknown"] += 1
        elif r.overall < 40:
            buckets["0-40"] += 1
        elif r.overall < 70:
            buckets["40-70"] += 1
        else:
            buckets["70-100"] += 1
    bucket_rows = "\n".join(f"| {k} | {v} |" for k, v in buckets.items())

    top_findings = _top_findings_across_run(summary)
    top_rows = "\n".join(
        f"| {count} | {cat} · {msg}" for count, cat, msg in top_findings[:5]
    ) or "_(none)_"

    return f"""\
# Site Scan — Run Summary

**Target mode:** `{target_name}`
**Input:** {"urls=" + str(len(urls)) if urls else f"limit={limit}"}
**Started:** `{started_at.isoformat()}`
**Finished:** `{finished_at.isoformat()}`
**Duration:** `{duration_s:.1f}s`

## Counts

| Metric | Value |
|---|---|
| Targets seen | {summary.targets_seen} |
| Scans persisted to ops.scans | {summary.scans_persisted} |
| Artifact-only (no matching lead) | {summary.artifacts_only} |
| Partial scans | {summary.partial_scans} |
| Skipped — SSRF | {summary.skipped_ssrf} |
| Skipped — unreachable | {summary.skipped_unreachable} |
| Average overall score | {"—" if avg_overall is None else f"{avg_overall:.1f}"} |

## Score distribution

| Bucket | Count |
|---|---|
{bucket_rows}

## Top findings across run

| Count | Category · Message |
|---|---|
{top_rows}
"""


def _top_findings_across_run(summary: ScannerSummary) -> list[tuple[int, str, str]]:
    counter: dict[tuple[str, str], int] = {}
    for result in summary.per_url_results:
        for f in result.findings:
            key = (f.category, f.smb_message)
            counter[key] = counter.get(key, 0) + 1
    items = [(count, cat, msg) for (cat, msg), count in counter.items()]
    items.sort(reverse=True)
    return items


if __name__ == "__main__":
    asyncio.run(scan_sites(limit=5))
