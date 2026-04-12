"""Lead Generator flow.

Input:  vertical, city, country, limit
Output: N rows inserted into the ``leads`` table

Phase 2 implementation TODO:
1. Query Google Maps Places API by vertical + city
2. For each result, extract name/website/phone/address
3. Canonicalize + validate website URL (SSRF-safe)
4. Hunter.io email lookup
5. Dedupe against existing leads by canonical_domain
6. UPSERT qualified leads
"""

from __future__ import annotations

import structlog
from prefect import flow

log = structlog.get_logger(__name__)


@flow(name="lead_generator")
def generate_leads(vertical: str, city: str, country: str, limit: int) -> int:
    """Generate leads and return the count inserted."""
    log.info(
        "lead_generator_start",
        vertical=vertical,
        city=city,
        country=country,
        limit=limit,
    )
    raise NotImplementedError("generate_leads flow is not yet implemented")
