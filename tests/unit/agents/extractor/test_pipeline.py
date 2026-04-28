"""Unit tests for the extractor orchestration.

Pure — no DB, no Playwright. Persistence + UPSERT idempotency are
exercised by the integration suite (separate; needs staging DB).
These tests only verify the error-classification + outcome shape.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from pipeline.agents.extractor.base import (
    ExtractionResult,
    ExtractionStrategyError,
)
from pipeline.agents.extractor.pipeline import (
    ERROR_CATEGORY_SSRF,
    ERROR_CATEGORY_STRATEGY,
    ERROR_CATEGORY_UNREACHABLE,
    extract_lead,
)
from pipeline.utils.browser import BrowserFetchError
from pipeline.utils.ssrf import UnsafeUrlError


@pytest.mark.asyncio
async def test_extract_lead_ssrf_returns_outcome_no_persist() -> None:
    lead_id = uuid.uuid4()
    with (
        patch(
            "pipeline.agents.extractor.pipeline.extract_url",
            new=AsyncMock(side_effect=UnsafeUrlError("private IP")),
        ),
        patch("pipeline.agents.extractor.pipeline._upsert_extraction") as upsert,
    ):
        outcome = await extract_lead(lead_id, "http://10.0.0.1")
    assert outcome.succeeded is False
    assert outcome.error_category == ERROR_CATEGORY_SSRF
    assert outcome.error_reason is not None
    assert "private IP" in outcome.error_reason
    upsert.assert_not_called()


@pytest.mark.asyncio
async def test_extract_lead_unreachable_returns_outcome_no_persist() -> None:
    lead_id = uuid.uuid4()
    with (
        patch(
            "pipeline.agents.extractor.pipeline.extract_url",
            new=AsyncMock(side_effect=BrowserFetchError("nav timeout")),
        ),
        patch("pipeline.agents.extractor.pipeline._upsert_extraction") as upsert,
    ):
        outcome = await extract_lead(lead_id, "https://example.com")
    assert outcome.succeeded is False
    assert outcome.error_category == ERROR_CATEGORY_UNREACHABLE
    upsert.assert_not_called()


@pytest.mark.asyncio
async def test_extract_lead_strategy_failure_returns_outcome_no_persist() -> None:
    lead_id = uuid.uuid4()
    with (
        patch(
            "pipeline.agents.extractor.pipeline.extract_url",
            new=AsyncMock(side_effect=ExtractionStrategyError("bad data")),
        ),
        patch("pipeline.agents.extractor.pipeline._upsert_extraction") as upsert,
    ):
        outcome = await extract_lead(lead_id, "https://example.com")
    assert outcome.succeeded is False
    assert outcome.error_category == ERROR_CATEGORY_STRATEGY
    upsert.assert_not_called()


@pytest.mark.asyncio
async def test_extract_lead_success_persists_once() -> None:
    lead_id = uuid.uuid4()
    result = ExtractionResult(
        business_name="Acme Movers",
        strategy_name="html_only",
        cost_usd=0.0,
    )
    with (
        patch(
            "pipeline.agents.extractor.pipeline.extract_url",
            new=AsyncMock(return_value=result),
        ),
        patch("pipeline.agents.extractor.pipeline._upsert_extraction") as upsert,
    ):
        outcome = await extract_lead(lead_id, "https://acme.com")
    assert outcome.succeeded is True
    assert outcome.error_category is None
    assert outcome.result is result
    upsert.assert_called_once_with(lead_id, result)


def test_extraction_result_round_trips_through_model_dump() -> None:
    """The flow stores ``model_dump(mode='json')`` into JSONB; ensure nested
    pydantic models (ServiceBlurb, Testimonial) survive the trip."""
    from pipeline.agents.extractor.base import ServiceBlurb, Testimonial

    original = ExtractionResult(
        business_name="Acme",
        services=[ServiceBlurb(name="Local Moving", blurb="Same-day quotes")],
        testimonials=[Testimonial(quote="Best movers ever", author="Jane D.")],
        brand_colors=["#112233"],
        strategy_name="html_only",
    )
    dumped = original.model_dump(mode="json")
    rehydrated = ExtractionResult.model_validate(dumped)
    assert rehydrated.services[0].name == "Local Moving"
    assert rehydrated.testimonials[0].author == "Jane D."
    assert rehydrated.brand_colors == ["#112233"]
