"""SQLAlchemy 2.x declarative base + shared column types.

Schemas:
    ops.*  — pipeline-owned operational tables (leads, scans, extractions,
             emails, suppression_list, events). Customer code reads some of
             these (preview page reads extractions) but should never write.
    app.*  — customer-facing surface (sites, payments). Web app reads and
             writes these; Stripe webhooks land here.

One deliberate exception to the boundary: ``ops.events`` accepts writes from
both the pipeline (agent audit trail) and the web side (Stripe webhook
events). That crossing is intentional; alternative is two ``events`` tables.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

OPS_SCHEMA = "ops"
APP_SCHEMA = "app"


class Base(DeclarativeBase):
    """Shared declarative base for every BetterSite model."""


class TimestampMixin:
    """created_at / updated_at columns managed by the database."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
