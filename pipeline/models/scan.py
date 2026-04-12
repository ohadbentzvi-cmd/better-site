"""Website Scanner output — one row per lead."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pipeline.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from pipeline.models.lead import Lead


class Scan(Base, TimestampMixin):
    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )

    # Overall
    score: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100
    pass_fail: Mapped[bool] = mapped_column(Boolean, nullable=False)
    issues_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)

    # Page speed
    pagespeed_mobile: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pagespeed_desktop: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Basic health checks
    has_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_mobile: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_analytics: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Screenshot of the current site (used by the before/after slider later)
    screenshot_r2_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    lead: Mapped["Lead"] = relationship(back_populates="scan")

    __table_args__ = (
        # One scan per lead — allows idempotent UPSERT by lead_id
        UniqueConstraint("lead_id", name="uq_scans_lead_id"),
    )
