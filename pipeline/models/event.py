"""Pipeline event log — the audit trail for every agent execution."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pipeline.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from pipeline.models.lead import Lead


class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )

    # e.g. "lead_generator.start", "scanner.complete", "extractor.claude_vision.error"
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)

    # Arbitrary context: error message, cost in USD, latency, model version, etc.
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    lead: Mapped["Lead"] = relationship(back_populates="events")

    __table_args__ = (
        Index("idx_events_lead_id_created", "lead_id", "created_at"),
        Index("idx_events_type", "event_type"),
    )
