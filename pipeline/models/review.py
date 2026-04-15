"""Analyst reviews — append-only opinions on leads and scans.

lead_reviews: approve/reject verdict + reason code (required on reject) +
optional note (required when reason_code is 'duplicate_or_other'). Latest row
per lead_id wins in the UI; history is preserved.

scan_reviews: free-text analyst reasoning about why a scan score is wrong.
No numeric override by design — the text is the calibration signal for
scanner tuning, the number would be arbitrary.

Both tables are append-only. "Change of mind" creates a new row rather than
mutating an old one. Invariants are enforced by Postgres CHECK constraints
(not app-layer only) so a pipeline bug cannot corrupt the review history.
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pipeline.models.base import OPS_SCHEMA, Base, TimestampMixin

if TYPE_CHECKING:
    from pipeline.models.analyst import Analyst
    from pipeline.models.lead import Lead
    from pipeline.models.scan import Scan


class LeadReviewVerdict(str, enum.Enum):
    approved = "approved"
    rejected = "rejected"


class LeadReviewReason(str, enum.Enum):
    not_icp = "not_icp"
    site_already_good = "site_already_good"
    site_broken_or_dead = "site_broken_or_dead"
    duplicate_or_other = "duplicate_or_other"


class LeadReview(Base, TimestampMixin):
    __tablename__ = "lead_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ops.leads.id", ondelete="CASCADE"),
        nullable=False,
    )
    analyst_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ops.analysts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    verdict: Mapped[LeadReviewVerdict] = mapped_column(
        Enum(LeadReviewVerdict, name="lead_review_verdict", schema=OPS_SCHEMA),
        nullable=False,
    )
    reason_code: Mapped[LeadReviewReason | None] = mapped_column(
        Enum(LeadReviewReason, name="lead_review_reason", schema=OPS_SCHEMA),
        nullable=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    lead: Mapped["Lead"] = relationship()
    analyst: Mapped["Analyst"] = relationship(back_populates="lead_reviews")

    __table_args__ = (
        CheckConstraint(
            # Approved: no reason, no special note rules.
            # Rejected: reason_code required; if duplicate_or_other, note required.
            "(verdict = 'approved' AND reason_code IS NULL) "
            "OR (verdict = 'rejected' "
            "    AND reason_code IS NOT NULL "
            "    AND (reason_code <> 'duplicate_or_other' "
            "         OR (note IS NOT NULL AND length(btrim(note)) > 0)))",
            name="lead_review_verdict_shape",
        ),
        Index("idx_lead_reviews_lead_id_created", "lead_id", "created_at"),
        {"schema": OPS_SCHEMA},
    )


class ScanReview(Base, TimestampMixin):
    __tablename__ = "scan_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ops.scans.id", ondelete="CASCADE"),
        nullable=False,
    )
    analyst_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ops.analysts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)

    scan: Mapped["Scan"] = relationship()
    analyst: Mapped["Analyst"] = relationship(back_populates="scan_reviews")

    __table_args__ = (
        CheckConstraint(
            "length(btrim(reasoning)) > 0",
            name="scan_review_reasoning_nonempty",
        ),
        Index("idx_scan_reviews_scan_id_created", "scan_id", "created_at"),
        {"schema": OPS_SCHEMA},
    )
