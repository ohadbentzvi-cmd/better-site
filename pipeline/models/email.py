"""Sent email record — one row per send (initial + follow-up are separate rows)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pipeline.models.base import OPS_SCHEMA, Base, TimestampMixin

if TYPE_CHECKING:
    from pipeline.models.lead import Lead


class EmailStatus(str, enum.Enum):
    queued = "queued"
    sent = "sent"
    delivered = "delivered"
    opened = "opened"
    clicked = "clicked"
    replied = "replied"
    bounced = "bounced"
    complained = "complained"
    suppressed = "suppressed"
    failed = "failed"


class Email(Base, TimestampMixin):
    __tablename__ = "emails"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.leads.id", ondelete="CASCADE"), nullable=False
    )

    # Which send in the sequence: 1 = initial, 2 = follow-up
    sequence_step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[EmailStatus] = mapped_column(
        Enum(EmailStatus, name="email_status", schema=OPS_SCHEMA),
        nullable=False,
        default=EmailStatus.queued,
    )

    # Which SalesAgentBackend sent this, and which inbox within it
    backend_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    smtp_inbox_used: Mapped[str | None] = mapped_column(String(255), nullable=True)

    lead: Mapped["Lead"] = relationship(back_populates="emails")

    __table_args__ = (
        Index("idx_emails_lead_id_step", "lead_id", "sequence_step"),
        Index("idx_emails_status_sent_at", "status", "sent_at"),
        {"schema": OPS_SCHEMA},
    )
