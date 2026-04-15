"""Stripe payment — one row per payment intent."""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pipeline.models.base import APP_SCHEMA, Base, TimestampMixin

if TYPE_CHECKING:
    from pipeline.models.lead import Lead


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    succeeded = "succeeded"
    refunded = "refunded"
    disputed = "disputed"
    failed = "failed"


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.leads.id", ondelete="RESTRICT"), nullable=False
    )

    # Stripe IDs — unique enforces webhook idempotency
    stripe_payment_intent_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )

    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status", schema=APP_SCHEMA),
        nullable=False,
        default=PaymentStatus.pending,
        index=True,
    )

    # Raw webhook payload stored for debugging + dispute handling
    raw_webhook: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    lead: Mapped["Lead"] = relationship(back_populates="payments")

    __table_args__ = (
        UniqueConstraint("stripe_payment_intent_id", name="uq_payments_pi"),
        {"schema": APP_SCHEMA},
    )
