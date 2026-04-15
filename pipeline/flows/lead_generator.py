"""Lead Generator flow.

Phase 1 demo: UPSERTs a single synthetic lead into ``ops.leads`` to prove
end-to-end DB connectivity from the Railway worker.

Phase 2 will replace the body with Google Maps Places → canonicalize →
Hunter.io → dedupe → UPSERT. The UPSERT pattern here is the one every
agent will use — ``INSERT ... ON CONFLICT DO UPDATE`` keyed on
``canonical_domain`` so Prefect retries are safe.
"""

from __future__ import annotations

import structlog
from prefect import flow
from sqlalchemy.dialects.postgresql import insert as pg_insert

from pipeline.db import session_scope
from pipeline.models import Lead, LeadStatus

log = structlog.get_logger(__name__)


@flow(name="lead-generation")
def generate_leads(
    vertical: str = "movers",
    city: str = "Austin",
    country: str = "US",
    limit: int = 10,
) -> int:
    """UPSERT one demo lead. Returns the number of rows touched (always 1)."""
    log.info(
        "lead_generation_start",
        vertical=vertical,
        city=city,
        country=country,
        limit=limit,
    )

    # Deterministic canonical_domain so re-running the flow UPSERTs the same row.
    canonical = f"demo-{vertical}-{city.lower()}.example"
    values = {
        "business_name": f"Demo {vertical.title()} of {city}",
        "vertical": vertical,
        "website_url": f"https://{canonical}",
        "canonical_domain": canonical,
        "email": f"hello@{canonical}",
        "city": city,
        "country": country,
        "source": "demo",
        "status": LeadStatus.new,
    }

    stmt = pg_insert(Lead).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["canonical_domain"],
        set_={
            "business_name": stmt.excluded.business_name,
            "vertical": stmt.excluded.vertical,
            "website_url": stmt.excluded.website_url,
            "email": stmt.excluded.email,
            "city": stmt.excluded.city,
            "country": stmt.excluded.country,
            "source": stmt.excluded.source,
        },
    )

    with session_scope() as session:
        session.execute(stmt)
        session.commit()

    log.info("lead_generation_upserted", canonical_domain=canonical)
    return 1


if __name__ == "__main__":
    generate_leads()
