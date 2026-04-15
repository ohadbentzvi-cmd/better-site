"""Pydantic schemas for the admin console API.

Explicit response models — never serialize raw JSONB blobs to the wire.
Curated projections only. If the scanner adds a field to raw_metrics
tomorrow, the admin contract does not silently shift.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from pipeline.models.lead import LeadStatus
from pipeline.models.review import LeadReviewReason, LeadReviewVerdict


class AnalystOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    username: str


class VerifyRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=512)


class VerifyResponse(BaseModel):
    analyst_id: uuid.UUID
    username: str


class ScanSummary(BaseModel):
    """Minimal scan projection for list rows."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    score: int | None
    score_performance: int | None
    score_seo: int | None
    score_ai_readiness: int | None
    score_security: int | None
    scan_partial: bool
    pass_fail: bool


class ScanDetail(ScanSummary):
    """Full scan projection for the lead detail page."""

    scanned_url: str | None
    issues: list[dict[str, Any]]
    key_metrics: dict[str, Any]
    pagespeed_mobile: int | None
    pagespeed_desktop: int | None
    scanned_at: datetime


# Keys we project from raw_metrics for the MetricsGrid.
_KEY_METRIC_FIELDS = (
    "lcp_ms",
    "cls",
    "tbt_ms",
    "fcp_ms",
    "ttfb_ms",
    "page_weight_kb",
)


def project_key_metrics(raw_metrics: dict[str, Any] | None) -> dict[str, Any]:
    """Return only the curated subset — never leak raw JSONB."""
    if not raw_metrics:
        return {}
    return {k: raw_metrics.get(k) for k in _KEY_METRIC_FIELDS if k in raw_metrics}


class LeadReviewSummary(BaseModel):
    """Compact review record for the list view (just the latest per lead)."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    verdict: LeadReviewVerdict
    reason_code: LeadReviewReason | None
    analyst_username: str
    created_at: datetime


class LeadReviewOut(LeadReviewSummary):
    """Full review record for the lead detail history."""

    note: str | None


class ScanReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    reasoning: str
    analyst_username: str
    created_at: datetime


class LeadRow(BaseModel):
    """List-view row. One row per lead with optional scan + latest review."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    business_name: str
    canonical_domain: str
    website_url: str
    vertical: str
    country: str
    status: LeadStatus
    email: str | None
    email_source: str | None
    created_at: datetime
    scan: ScanSummary | None
    latest_review: LeadReviewSummary | None


class LeadsListResponse(BaseModel):
    items: list[LeadRow]
    next_cursor: str | None
    total: int


class LeadDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    business_name: str
    canonical_domain: str
    website_url: str
    vertical: str
    city: str | None
    state: str | None
    country: str
    email: str | None
    email_source: str | None
    phone: str | None
    source: str
    status: LeadStatus
    created_at: datetime
    scan: ScanDetail | None
    lead_reviews: list[LeadReviewOut]
    scan_reviews: list[ScanReviewOut]


class ReviewCreate(BaseModel):
    verdict: LeadReviewVerdict
    reason_code: LeadReviewReason | None = None
    note: str | None = None


class ScanFeedbackCreate(BaseModel):
    reasoning: str = Field(min_length=1, max_length=5000)


class EmailBackfillRequest(BaseModel):
    email: EmailStr


class ReviewedOut(BaseModel):
    """Returned after a successful review / feedback / email mutation."""

    ok: Literal[True] = True
    id: uuid.UUID
