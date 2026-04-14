"""Lead Generator flow.

Phase 1 demo: prints hello world. Real implementation lands in Phase 2.
"""

from __future__ import annotations

import structlog
from prefect import flow

log = structlog.get_logger(__name__)


@flow(name="lead-generation")
def generate_leads(vertical: str = "movers", city: str = "Austin", country: str = "US", limit: int = 10) -> str:
    msg = f"hello world from lead-generation (vertical={vertical}, city={city}, country={country}, limit={limit})"
    log.info("lead_generation_demo", msg=msg)
    print(msg)
    return msg


if __name__ == "__main__":
    generate_leads()
