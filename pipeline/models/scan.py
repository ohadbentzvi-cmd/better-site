"""Website Scanner output — one row per lead.

``overall score`` is NULL when at least one dimension was unmeasurable
(e.g. PageSpeed API failed). ``scan_partial`` is True in that case and
tells downstream code / dashboards that this lead's numbers are
incomplete.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pipeline.models.base import OPS_SCHEMA, Base, TimestampMixin

if TYPE_CHECKING:
    from pipeline.models.lead import Lead


class Scan(Base, TimestampMixin):
    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.leads.id", ondelete="CASCADE"), nullable=False
    )

    scanned_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Composite 0-100; NULL when scan_partial is True.
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pass_fail: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Per-dimension scores; NULL if that dimension was unmeasurable.
    score_performance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_seo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_ai_readiness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_security: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Structured findings for cold-email copy + admin review.
    issues_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)

    # Raw metrics — LCP, CLS, TBT, FCP, TTFB, page_weight, etc.
    raw_metrics: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    # PageSpeed category scores (mobile + desktop).
    pagespeed_mobile: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pagespeed_desktop: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pagespeed_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    # True when any dimension was unmeasurable. Overall score is NULL here.
    scan_partial: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Legacy basic health checks kept for backward compatibility in admin UI.
    has_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_mobile: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_analytics: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Screenshot R2 key — unused in Phase 2.5; screenshots land in Prefect
    # artifacts only until object storage is chosen in Phase 3.
    screenshot_r2_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    lead: Mapped["Lead"] = relationship(back_populates="scan")

    __table_args__ = (
        # One scan per lead — allows idempotent UPSERT by lead_id
        UniqueConstraint("lead_id", name="uq_scans_lead_id"),
        {"schema": OPS_SCHEMA},
    )
