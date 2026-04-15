"""Core types for the Lead Generator.

``LeadSource`` is the pluggable interface. ``BBBSource`` implements it
today; ``FMCSASource`` / ``GoogleMapsSource`` implement it later without
touching the orchestrator or the flow.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class RawLead(BaseModel):
    """Source-agnostic lead payload produced by a ``LeadSource``.

    The pipeline canonicalizes + SSRF-checks + UPSERTs. Sources don't
    need to know anything downstream.
    """

    business_name: str
    website_url: str  # raw, pre-canonicalization
    vertical: str    # internal tag: "movers" / "lawyers" / ...
    country: str     # ISO alpha-2, e.g. "US"
    state: str | None = None   # ISO 3166-2 subdivision, e.g. "TX"
    city: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    source: str                 # "bbb" / "fmcsa" / ...
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    email_source: str | None = None  # "bbb" / "extracted" / "fallback_info_at" / None


@runtime_checkable
class LeadSource(Protocol):
    """Any class that can produce ``RawLead`` instances.

    Implementations live under ``pipeline.agents.lead_generator.sources.*``
    and register themselves in ``sources.SOURCES``.
    """

    name: str  # "bbb" / "fmcsa" / "google_maps"

    def fetch(
        self,
        *,
        vertical: str,
        state: str,
        city: str,
        max_pages: int | None = None,
    ) -> AsyncIterator[RawLead]:
        """Yield ``RawLead`` instances. Order is source-defined."""
        ...


__all__ = ["LeadSource", "RawLead"]
