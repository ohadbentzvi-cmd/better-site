"""Information Extractor output — one row per lead.

The content_json shape is defined by ``pipeline.agents.extractor.schema.ExtractionResult``.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pipeline.models.base import OPS_SCHEMA, Base, TimestampMixin

if TYPE_CHECKING:
    from pipeline.models.lead import Lead


class Extraction(Base, TimestampMixin):
    __tablename__ = "extractions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.leads.id", ondelete="CASCADE"), nullable=False
    )

    # Strategy used to produce this extraction (html_only, vision_full, hybrid, gmb_first)
    strategy_name: Mapped[str] = mapped_column(String(64), nullable=False)

    # Structured content (name, tagline, copy, services, contact, socials, etc.)
    content_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # Image references (logo, hero, etc.) — R2 keys + metadata
    images_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # Brand colors as list of hex strings, e.g. ["#C41E3A", "#FFFFFF", "#0A0A0A"]
    brand_colors: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    # Version of the vision model used, if any
    vision_model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    lead: Mapped["Lead"] = relationship(back_populates="extraction")

    __table_args__ = (
        UniqueConstraint("lead_id", name="uq_extractions_lead_id"),
        {"schema": OPS_SCHEMA},
    )
