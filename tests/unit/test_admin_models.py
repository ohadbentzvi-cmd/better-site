"""Model-level unit tests for the admin console tables.

Pure metadata tests — no DB connection. Verifies that the CHECK constraints
are registered on the model (they're enforced by Postgres at write time;
integration tests against staging DB exercise the actual enforcement).
"""

from __future__ import annotations

from pipeline.models.analyst import Analyst, LoginAttempt
from pipeline.models.review import (
    LeadReview,
    LeadReviewReason,
    LeadReviewVerdict,
    ScanReview,
)


def _constraint_names(model_cls) -> set[str]:
    return {c.name for c in model_cls.__table__.constraints if c.name}


def test_lead_review_verdict_shape_constraint_registered() -> None:
    assert "lead_review_verdict_shape" in _constraint_names(LeadReview)


def test_scan_review_nonempty_constraint_registered() -> None:
    assert "scan_review_reasoning_nonempty" in _constraint_names(ScanReview)


def test_analyst_table_columns() -> None:
    cols = {c.name for c in Analyst.__table__.columns}
    assert {
        "id",
        "username",
        "password_hash",
        "active",
        "last_login_at",
        "created_at",
        "updated_at",
    }.issubset(cols)


def test_analyst_username_is_unique() -> None:
    username_col = Analyst.__table__.c.username
    assert username_col.unique is True


def test_login_attempts_indexed_for_rate_limiting() -> None:
    """The (username, attempt_at) index is what makes the rate-limit query fast."""
    idx_cols = {
        tuple(c.name for c in idx.columns) for idx in LoginAttempt.__table__.indexes
    }
    assert ("username", "attempt_at") in idx_cols


def test_lead_review_verdict_enum_values() -> None:
    assert {v.value for v in LeadReviewVerdict} == {"approved", "rejected"}


def test_lead_review_reason_enum_values() -> None:
    assert {v.value for v in LeadReviewReason} == {
        "not_icp",
        "site_already_good",
        "site_broken_or_dead",
        "duplicate_or_other",
    }


def test_scan_review_has_analyst_fk() -> None:
    fks = {fk.target_fullname for fk in ScanReview.__table__.foreign_keys}
    assert "ops.analysts.id" in fks
    assert "ops.scans.id" in fks


def test_lead_review_has_both_fks() -> None:
    fks = {fk.target_fullname for fk in LeadReview.__table__.foreign_keys}
    assert "ops.analysts.id" in fks
    assert "ops.leads.id" in fks
