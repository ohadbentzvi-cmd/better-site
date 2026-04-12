"""SQLAlchemy models — single source of truth for the DB schema.

Importing this module registers every model on the shared ``Base.metadata``
so Alembic autogeneration can pick them up.
"""

from pipeline.models.base import Base
from pipeline.models.email import Email, EmailStatus
from pipeline.models.event import Event
from pipeline.models.extraction import Extraction
from pipeline.models.lead import Lead, LeadStatus
from pipeline.models.payment import Payment, PaymentStatus
from pipeline.models.scan import Scan
from pipeline.models.site import Site, SiteStatus
from pipeline.models.suppression import SuppressionEntry, SuppressionReason

__all__ = [
    "Base",
    "Email",
    "EmailStatus",
    "Event",
    "Extraction",
    "Lead",
    "LeadStatus",
    "Payment",
    "PaymentStatus",
    "Scan",
    "Site",
    "SiteStatus",
    "SuppressionEntry",
    "SuppressionReason",
]
