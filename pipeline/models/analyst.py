"""Analyst accounts for the admin review console.

An analyst is a human reviewer with a username + bcrypt'd password. Analysts
produce lead_reviews and scan_reviews; those are append-only records carrying
their analyst_id as attribution.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pipeline.models.base import OPS_SCHEMA, Base, TimestampMixin

if TYPE_CHECKING:
    from pipeline.models.review import LeadReview, ScanReview


class Analyst(Base, TimestampMixin):
    __tablename__ = "analysts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    is_superadmin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    lead_reviews: Mapped[list["LeadReview"]] = relationship(back_populates="analyst")
    scan_reviews: Mapped[list["ScanReview"]] = relationship(back_populates="analyst")

    __table_args__ = ({"schema": OPS_SCHEMA},)


class LoginAttempt(Base):
    """Append-only log of every login attempt, successful or not.

    Used for rate limiting (5 failed attempts / 15 min / username) and for
    security audit. Unknown usernames are still recorded so we don't leak
    enumeration information via timing.
    """

    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )

    __table_args__ = (
        Index("idx_login_attempts_username_time", "username", "attempt_at"),
        {"schema": OPS_SCHEMA},
    )
