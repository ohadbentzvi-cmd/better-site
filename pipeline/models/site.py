"""Generated website — one row per lead.

The preview page at ``/preview/[slug]`` reads from this table.
After 48h, ``expires_at`` causes the route to 404.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pipeline.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from pipeline.models.lead import Lead


class SiteStatus(str, enum.Enum):
    draft = "draft"
    review_pending = "review_pending"
    approved = "approved"
    live = "live"
    expired = "expired"
    purchased = "purchased"


class Site(Base, TimestampMixin):
    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )

    # Unguessable slug (nanoid(12)) used in the preview URL
    slug: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)

    # Full preview URL, derived from APP_BASE_URL + slug
    preview_url: Mapped[str] = mapped_column(String(1024), nullable=False)

    status: Mapped[SiteStatus] = mapped_column(
        Enum(SiteStatus, name="site_status"),
        nullable=False,
        default=SiteStatus.draft,
        index=True,
    )

    # 48h after generation by default. NULL = permanent (post-purchase).
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lead: Mapped["Lead"] = relationship(back_populates="site")

    __table_args__ = (
        UniqueConstraint("lead_id", name="uq_sites_lead_id"),
        Index(
            "idx_sites_expires_at",
            "expires_at",
            postgresql_where="expires_at IS NOT NULL",
        ),
    )
