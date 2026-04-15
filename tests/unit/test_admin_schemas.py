"""Unit tests for api/schemas/admin.py pydantic models.

Tests the curated projection of raw_metrics (never leak raw JSONB) and
the request-body validation for review + scan-feedback + email-backfill.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.schemas.admin import (
    EmailBackfillRequest,
    ReviewCreate,
    ScanFeedbackCreate,
    project_key_metrics,
)
from pipeline.models.review import LeadReviewReason, LeadReviewVerdict


class TestProjectKeyMetrics:
    def test_curated_fields_only(self) -> None:
        raw = {
            "lcp_ms": 2400,
            "cls": 0.1,
            "tbt_ms": 150,
            "fcp_ms": 1200,
            "ttfb_ms": 200,
            "page_weight_kb": 1800,
            # Fields that must NOT leak.
            "internal_debug_trace": "secret",
            "pagespeed_raw_audit": {"huge": "blob"},
        }
        result = project_key_metrics(raw)
        assert set(result.keys()) == {
            "lcp_ms",
            "cls",
            "tbt_ms",
            "fcp_ms",
            "ttfb_ms",
            "page_weight_kb",
        }
        assert "internal_debug_trace" not in result
        assert "pagespeed_raw_audit" not in result

    def test_missing_fields_absent(self) -> None:
        raw = {"lcp_ms": 1000}
        assert project_key_metrics(raw) == {"lcp_ms": 1000}

    def test_none_input(self) -> None:
        assert project_key_metrics(None) == {}

    def test_empty_dict(self) -> None:
        assert project_key_metrics({}) == {}


class TestReviewCreate:
    def test_approved_no_reason(self) -> None:
        body = ReviewCreate(verdict=LeadReviewVerdict.approved)
        assert body.verdict == LeadReviewVerdict.approved
        assert body.reason_code is None
        assert body.note is None

    def test_rejected_with_reason(self) -> None:
        body = ReviewCreate(
            verdict=LeadReviewVerdict.rejected,
            reason_code=LeadReviewReason.not_icp,
        )
        assert body.verdict == LeadReviewVerdict.rejected
        assert body.reason_code == LeadReviewReason.not_icp

    def test_rejected_duplicate_with_note(self) -> None:
        body = ReviewCreate(
            verdict=LeadReviewVerdict.rejected,
            reason_code=LeadReviewReason.duplicate_or_other,
            note="same domain as lead XYZ",
        )
        assert body.note == "same domain as lead XYZ"

    def test_invalid_verdict(self) -> None:
        with pytest.raises(ValidationError):
            ReviewCreate(verdict="maybe")  # type: ignore[arg-type]

    def test_invalid_reason(self) -> None:
        with pytest.raises(ValidationError):
            ReviewCreate(
                verdict=LeadReviewVerdict.rejected,
                reason_code="not_a_real_reason",  # type: ignore[arg-type]
            )


class TestScanFeedbackCreate:
    def test_happy_path(self) -> None:
        body = ScanFeedbackCreate(reasoning="Score too high because X")
        assert body.reasoning == "Score too high because X"

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ScanFeedbackCreate(reasoning="")

    def test_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ScanFeedbackCreate(reasoning="x" * 5001)


class TestEmailBackfillRequest:
    def test_valid_email(self) -> None:
        body = EmailBackfillRequest(email="owner@example.com")
        assert str(body.email) == "owner@example.com"

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "not-an-email",
            "missing@domain",
            "@missing-local.com",
            "has space@foo.com",
        ],
    )
    def test_invalid_email(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            EmailBackfillRequest(email=bad)
