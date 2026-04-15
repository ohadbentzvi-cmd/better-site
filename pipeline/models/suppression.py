"""Suppression list — email + domain blocklist checked before every send."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from pipeline.models.base import OPS_SCHEMA, Base, TimestampMixin


class SuppressionReason(str, enum.Enum):
    unsubscribe = "unsubscribe"
    bounce = "bounce"
    complaint = "complaint"
    manual = "manual"
    competitor = "competitor"
    existing_customer = "existing_customer"


class SuppressionEntry(Base, TimestampMixin):
    __tablename__ = "suppression_list"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Either email OR domain (or both). Email is lowercased before insert.
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)

    reason: Mapped[SuppressionReason] = mapped_column(
        Enum(SuppressionReason, name="suppression_reason", schema=OPS_SCHEMA),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_suppression_email", "email", unique=True, postgresql_where="email IS NOT NULL"),
        Index("idx_suppression_domain", "domain"),
        {"schema": OPS_SCHEMA},
    )
