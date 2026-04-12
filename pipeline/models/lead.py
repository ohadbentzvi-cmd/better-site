"""Lead model — the central entity of the pipeline.

State machine:
    new → scanned → extracted → built → review_pending →
      approved → emailed → followed_up → opened → clicked → purchased
                                      └→ rejected
                                      └→ bounced
                                      └→ unsubscribed
                                      └→ suppressed
                                      └→ bad_email
                                      └→ unreachable
                                      └→ skipped_language
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pipeline.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from pipeline.models.email import Email
    from pipeline.models.event import Event
    from pipeline.models.extraction import Extraction
    from pipeline.models.payment import Payment
    from pipeline.models.scan import Scan
    from pipeline.models.site import Site


class LeadStatus(str, enum.Enum):
    new = "new"
    scanned = "scanned"
    extracted = "extracted"
    built = "built"
    review_pending = "review_pending"
    approved = "approved"
    emailed = "emailed"
    followed_up = "followed_up"
    opened = "opened"
    clicked = "clicked"
    purchased = "purchased"
    rejected = "rejected"
    bounced = "bounced"
    unsubscribed = "unsubscribed"
    suppressed = "suppressed"
    bad_email = "bad_email"
    unreachable = "unreachable"
    skipped_language = "skipped_language"


class Lead(Base, TimestampMixin):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Business info
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    vertical: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Website
    website_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    canonical_domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Contact
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Geography
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    country: Mapped[str] = mapped_column(String(8), nullable=False, index=True)  # ISO alpha-2

    # Provenance
    source: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. "google_maps"

    # Pipeline state
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, name="lead_status"),
        nullable=False,
        default=LeadStatus.new,
        index=True,
    )

    # Relationships
    scan: Mapped["Scan | None"] = relationship(back_populates="lead", uselist=False)
    extraction: Mapped["Extraction | None"] = relationship(back_populates="lead", uselist=False)
    site: Mapped["Site | None"] = relationship(back_populates="lead", uselist=False)
    emails: Mapped[list["Email"]] = relationship(back_populates="lead")
    payments: Mapped[list["Payment"]] = relationship(back_populates="lead")
    events: Mapped[list["Event"]] = relationship(back_populates="lead")

    __table_args__ = (
        Index("idx_leads_vertical_country", "vertical", "country"),
    )
