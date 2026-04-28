"""Extractor orchestration.

- :func:`extract_url` runs the shared pre-fetch (Playwright render →
  HTML + screenshot) and delegates to the configured strategy. Pure —
  no DB writes.
- :func:`extract_lead` wraps :func:`extract_url` with an UPSERT into
  ``ops.extractions``. Idempotent under Prefect retries via
  ``ON CONFLICT (lead_id) DO UPDATE``.
- Errors are converted into a typed :class:`ExtractorOutcome` so a
  single bad site cannot abort a batch flow run.

Lead status transitions (``new``/``scanned`` → ``extracted``) belong to
the flow layer, not here — this module is responsible only for the
extraction row.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from pipeline.agents.extractor import get_strategy
from pipeline.agents.extractor.base import (
    ExtractionResult,
    ExtractionStrategyError,
)
from pipeline.config import get_settings
from pipeline.db import session_scope
from pipeline.models import Extraction
from pipeline.utils.browser import BrowserFetchError, render_page
from pipeline.utils.ssrf import UnsafeUrlError, assert_safe_url

log = structlog.get_logger(__name__)


# Top-level columns on ops.extractions; everything else in ExtractionResult
# is stored under content_json so future schema additions don't require a
# migration.
_TOP_LEVEL_FIELDS = frozenset(
    {
        "logo_r2_key",
        "hero_r2_key",
        "brand_colors",
        "strategy_name",
        "vision_model_version",
        "prompt_version",
        "cost_usd",
    }
)


ERROR_CATEGORY_SSRF = "ssrf"
ERROR_CATEGORY_UNREACHABLE = "unreachable"
ERROR_CATEGORY_STRATEGY = "strategy"


@dataclass(frozen=True)
class ExtractorOutcome:
    """Result of one ``extract_lead`` attempt."""

    lead_id: uuid.UUID
    url: str
    succeeded: bool
    error_category: str | None = None
    error_reason: str | None = None
    result: ExtractionResult | None = None


async def extract_url(url: str, *, strategy_name: str | None = None) -> ExtractionResult:
    """Render the page and run the configured strategy against it.

    Raises:
        UnsafeUrlError: SSRF check rejected the URL.
        BrowserFetchError: page is genuinely unreachable.
        ExtractionStrategyError: strategy raised a recognized failure.
    """
    assert_safe_url(url)
    name = strategy_name or get_settings().EXTRACTION_STRATEGY
    strategy = get_strategy(name)

    log.info("extractor.render_start", url=url, strategy=name)
    rendered = await render_page(url)
    log.info(
        "extractor.render_complete",
        url=url,
        html_bytes=len(rendered.html),
        screenshot_bytes=len(rendered.desktop_png),
    )

    return strategy.extract(
        url=url,
        html=rendered.html,
        screenshot_png=rendered.desktop_png,
    )


async def extract_lead(lead_id: uuid.UUID, url: str) -> ExtractorOutcome:
    """Extract one lead's site and UPSERT into ``ops.extractions``.

    Recoverable errors (SSRF, unreachable, strategy failure) are caught
    and returned as ``ExtractorOutcome(succeeded=False, error_reason=...)``.
    Unexpected errors propagate so Prefect can retry the task.
    """
    try:
        result = await extract_url(url)
    except UnsafeUrlError as e:
        log.warning("extractor.skip_ssrf", lead_id=str(lead_id), url=url, error=str(e))
        return ExtractorOutcome(
            lead_id, url, succeeded=False,
            error_category=ERROR_CATEGORY_SSRF, error_reason=str(e),
        )
    except BrowserFetchError as e:
        log.warning(
            "extractor.unreachable", lead_id=str(lead_id), url=url, error=str(e)
        )
        return ExtractorOutcome(
            lead_id, url, succeeded=False,
            error_category=ERROR_CATEGORY_UNREACHABLE, error_reason=str(e),
        )
    except ExtractionStrategyError as e:
        log.warning(
            "extractor.strategy_failed",
            lead_id=str(lead_id),
            url=url,
            error=str(e),
        )
        return ExtractorOutcome(
            lead_id, url, succeeded=False,
            error_category=ERROR_CATEGORY_STRATEGY, error_reason=str(e),
        )

    await asyncio.to_thread(_upsert_extraction, lead_id, result)
    log.info(
        "extractor.persisted",
        lead_id=str(lead_id),
        strategy=result.strategy_name,
        logo_set=result.logo_r2_key is not None,
        hero_set=result.hero_r2_key is not None,
        cost_usd=result.cost_usd,
    )
    return ExtractorOutcome(lead_id, url, succeeded=True, result=result)


def _upsert_extraction(lead_id: uuid.UUID, result: ExtractionResult) -> None:
    """``INSERT ... ON CONFLICT (lead_id) DO UPDATE``. Idempotent per Prefect contract."""
    content_json = result.model_dump(exclude=_TOP_LEVEL_FIELDS, mode="json")
    images_json: dict[str, str | None] = {
        "logo_r2_key": result.logo_r2_key,
        "hero_r2_key": result.hero_r2_key,
    }
    values: dict[str, Any] = {
        "lead_id": lead_id,
        "strategy_name": result.strategy_name,
        "content_json": content_json,
        "images_json": images_json,
        "brand_colors": result.brand_colors,
        "vision_model_version": result.vision_model_version,
        "prompt_version": result.prompt_version,
        "cost_usd": result.cost_usd,
    }
    stmt = pg_insert(Extraction).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["lead_id"],
        set_={k: stmt.excluded[k] for k in values if k != "lead_id"},
    )
    with session_scope() as session:
        session.execute(stmt)
        session.commit()


__all__ = [
    "ERROR_CATEGORY_SSRF",
    "ERROR_CATEGORY_STRATEGY",
    "ERROR_CATEGORY_UNREACHABLE",
    "ExtractorOutcome",
    "extract_lead",
    "extract_url",
]
